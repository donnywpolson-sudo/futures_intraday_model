#!/usr/bin/env python3
"""Build a console-only downstream Phase 3 label approval gate for ES 2026."""

from __future__ import annotations

import argparse
import ast
import json
import shlex
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_gates import file_sha256  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_gap_gate_policy_review as gap_review  # noqa: E402
from scripts.validation import build_local_trade_es2026_p1_repair_plan as repair_plan_gate  # noqa: E402


STAGE = "local_trade_es2026_p1_downstream_label_gate"
STATUS_READY = "REVIEW_READY_ES2026_P1_DOWNSTREAM_LABEL_GATE"
STATUS_NO_GO = "NO_GO_ES2026_P1_DOWNSTREAM_LABEL_GATE"
DECISION_GATE_ONLY = "es2026_p1_downstream_label_gate_only_no_execution"
DECISION_BLOCKED = "es2026_p1_downstream_label_gate_blocked"

TARGET_MARKET = repair_plan_gate.TARGET_MARKET
TARGET_YEAR = repair_plan_gate.TARGET_YEAR
TARGET_PROFILE = repair_plan_gate.DEFAULT_PROFILE
DEFAULT_CANDIDATE_CAUSAL_ROOT = Path(
    "data/causally_gated_normalized/local_trade_es2026_p1_candidate"
)
DEFAULT_LABEL_OUTPUT_ROOT = Path("data/labeled/local_trade_es2026_p1_candidate")
DEFAULT_LABEL_REPORTS_ROOT = Path("reports/labels/local_trade_es2026_p1_candidate")
DEFAULT_BUILD_REPORTS_ROOT = gap_review.DEFAULT_BUILD_REPORTS_ROOT
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_LABEL_SCRIPT = Path("scripts/phase3_labels/build_labels.py")
DEFAULT_ACCEPTED_READINESS_EXCEPTIONS = DEFAULT_PROFILE_CONFIG
DEFAULT_TIMEOUT_SECONDS = 900
FALSE_APPROVAL_FLAGS = repair_plan_gate.FALSE_APPROVAL_FLAGS + (
    "label_build_approved",
    "feature_matrix_build_approved",
)
REQUIRED_LABEL_FLAGS = {
    "--profile",
    "--input-root",
    "--output-root",
    "--reports-root",
    "--costs-config",
    "--profile-config",
    "--accepted-readiness-exceptions",
    "--markets",
    "--years",
    "--causal-base-manifest",
}
FORBIDDEN_LABEL_FLAGS: set[str] = set()
EXPECTED_ACCEPTED_WARNING = "statistics enrichment sparse: missing_rows=6 stale_rows=6"
EXPECTED_ACCEPTED_EXCEPTION_CATEGORY = "statistics_enrichment_sparse"
EXPECTED_ACCEPTED_EXCEPTION_REASON = (
    "bounded_es2026_statistics_enrichment_sparse_accepted_warning_packet_20260703"
)
EXPECTED_ACCEPTED_EVIDENCE_PATHS = [
    "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.json",
    "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.md",
]
FORBIDDEN_ACTIONS = (
    "phase3_label_execution_without_approval",
    "feature_matrix_build",
    "wfa_or_modeling",
    "metrics_or_predictions",
    "proof_scan",
    "provider_download_or_cost_diagnostic",
    "canonical_data_mutation",
    "candidate_raw_rewrite",
    "causal_base_build_or_rerun",
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


def command_path(path: Path, repo_root: Path) -> Path:
    return Path(rel(path, repo_root))


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


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


def _read_yaml_object(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, Mapping) else {}


def _summary(report: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, Mapping) else {}


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


def _git_ignored_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
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


def _declared_cli_flags(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "add_argument":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                flags.add(arg.value)
    return flags


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


def _int_count(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _expected_label_artifacts(*, output_root: Path, reports_root: Path) -> list[str]:
    return sorted(
        {
            (output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet").as_posix(),
            (reports_root / "label_manifest.json").as_posix(),
            (reports_root / "label_report.json").as_posix(),
        }
    )


def _label_command(
    *,
    input_root: Path,
    output_root: Path,
    reports_root: Path,
    causal_base_manifest: Path,
    profile_config: Path,
    costs_config: Path,
    accepted_readiness_exceptions: Path,
) -> str:
    return (
        "python -m scripts.phase3_labels.build_labels "
        f"--profile {TARGET_PROFILE} "
        f"--input-root {input_root.as_posix()} "
        f"--output-root {output_root.as_posix()} "
        f"--reports-root {reports_root.as_posix()} "
        f"--costs-config {costs_config.as_posix()} "
        f"--profile-config {profile_config.as_posix()} "
        f"--causal-base-manifest {causal_base_manifest.as_posix()} "
        f"--accepted-readiness-exceptions {accepted_readiness_exceptions.as_posix()} "
        f"--markets {TARGET_MARKET} "
        f"--years {TARGET_YEAR}"
    )


def _command_failures(
    command: str,
    *,
    input_root: Path,
    output_root: Path,
    reports_root: Path,
    causal_base_manifest: Path,
    profile_config: Path,
    costs_config: Path,
    accepted_readiness_exceptions: Path,
) -> list[str]:
    failures: list[str] = []
    argv = shlex.split(command)
    argv_set = set(argv)
    if argv[:3] != ["python", "-m", "scripts.phase3_labels.build_labels"]:
        failures.append("command does not invoke Phase 3 labels")
    for flag in FORBIDDEN_LABEL_FLAGS:
        if flag in argv_set:
            failures.append(f"forbidden label argument present: {flag}")
    expected = {
        "--profile": TARGET_PROFILE,
        "--input-root": input_root.as_posix(),
        "--output-root": output_root.as_posix(),
        "--reports-root": reports_root.as_posix(),
        "--costs-config": costs_config.as_posix(),
        "--profile-config": profile_config.as_posix(),
        "--causal-base-manifest": causal_base_manifest.as_posix(),
        "--accepted-readiness-exceptions": accepted_readiness_exceptions.as_posix(),
        "--markets": TARGET_MARKET,
        "--years": str(TARGET_YEAR),
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


def _profile_scope_ok(profile_config: Path) -> dict[str, Any]:
    payload = _read_yaml_object(profile_config)
    profiles = payload.get("profiles")
    profile = profiles.get(TARGET_PROFILE) if isinstance(profiles, Mapping) else None
    if not isinstance(profile, Mapping):
        return {"status": "FAIL", "reason": f"missing profile {TARGET_PROFILE}"}
    markets = profile.get("markets")
    years = profile.get("years")
    market_values = [str(item) for item in markets] if isinstance(markets, list) else []
    year_values = [int(item) for item in years] if isinstance(years, list) else []
    return {
        "status": "PASS" if TARGET_MARKET in market_values and TARGET_YEAR in year_values else "FAIL",
        "profile": TARGET_PROFILE,
        "target_market_in_profile": TARGET_MARKET in market_values,
        "target_year_in_profile": TARGET_YEAR in year_values,
    }


def _cost_evidence(costs_config: Path) -> dict[str, Any]:
    payload = _read_yaml_object(costs_config)
    markets = payload.get("markets")
    config = markets.get(TARGET_MARKET) if isinstance(markets, Mapping) else None
    if not isinstance(config, Mapping):
        return {"status": "FAIL", "market": TARGET_MARKET, "reason": "missing market cost config"}
    return {
        "status": "PASS",
        "market": TARGET_MARKET,
        "tick_size": config.get("tick_size"),
        "tick_value": config.get("tick_value"),
        "point_value": config.get("point_value"),
        "cost_source": config.get("cost_source"),
        "provisional": bool(config.get("provisional", True)),
        "estimated_cost_ticks": config.get("round_turn_cost_ticks"),
    }


def _accepted_warning_packet_evidence(profile_config: Path) -> dict[str, Any]:
    payload = _read_yaml_object(profile_config)
    profiles = payload.get("profiles")
    profile = profiles.get(TARGET_PROFILE) if isinstance(profiles, Mapping) else None
    if not isinstance(profile, Mapping):
        return {"status": "FAIL", "reason": f"missing profile {TARGET_PROFILE}"}
    exceptions = profile.get("accepted_readiness_exceptions")
    if not isinstance(exceptions, list):
        return {"status": "FAIL", "reason": "missing accepted_readiness_exceptions list"}
    matching = [
        item
        for item in exceptions
        if isinstance(item, Mapping)
        and item.get("market") == TARGET_MARKET
        and item.get("year") == TARGET_YEAR
        and item.get("category") == EXPECTED_ACCEPTED_EXCEPTION_CATEGORY
    ]
    if len(exceptions) != 1 or len(matching) != 1:
        return {
            "status": "FAIL",
            "profile_exception_count": len(exceptions),
            "matching_exception_count": len(matching),
            "reason": "ES 2026 packet is not exact single-scope evidence",
        }
    packet = matching[0]
    expected = {
        "category": EXPECTED_ACCEPTED_EXCEPTION_CATEGORY,
        "market": TARGET_MARKET,
        "year": TARGET_YEAR,
        "reason": EXPECTED_ACCEPTED_EXCEPTION_REASON,
        "evidence_paths": EXPECTED_ACCEPTED_EVIDENCE_PATHS,
        "warning_prefixes": [EXPECTED_ACCEPTED_WARNING],
    }
    mismatches = {
        key: {"observed": packet.get(key), "expected": value}
        for key, value in expected.items()
        if packet.get(key) != value
    }
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "profile": TARGET_PROFILE,
        "accepted_warning": EXPECTED_ACCEPTED_WARNING,
        "packet": {key: packet.get(key) for key in expected},
        "mismatches": mismatches,
    }


def _arg_value(argv: Sequence[str], flag: str) -> str | None:
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def _manifest_evidence(
    *,
    repo_root: Path,
    manifest_path: Path,
    expected_output_root: Path,
) -> tuple[dict[str, Any], str | None]:
    manifest, error = _read_json_object(manifest_path)
    if error or manifest is None:
        return {"status": "FAIL", "error": error}, error
    outputs = manifest.get("outputs")
    first_output = outputs[0] if isinstance(outputs, list) and outputs and isinstance(outputs[0], Mapping) else {}
    output_path = expected_output_root / TARGET_MARKET / f"{TARGET_YEAR}.parquet"
    output_hashes = manifest.get("output_file_hashes")
    output_hash = None
    if isinstance(output_hashes, Mapping):
        output_hash = output_hashes.get(rel(output_path, repo_root)) or output_hashes.get(output_path.as_posix())
    actual_hash = file_sha256(output_path) if output_path.exists() else None
    return {
        "status": "PASS",
        "path": rel(manifest_path, repo_root),
        "manifest_status": manifest.get("status"),
        "stage": manifest.get("stage"),
        "profile": manifest.get("profile"),
        "resolved_profile": manifest.get("resolved_profile"),
        "processed_market_year_count": manifest.get("processed_market_year_count"),
        "processed_market_years": manifest.get("processed_market_years"),
        "accepted_exception_count": manifest.get("accepted_exception_count"),
        "accepted_exception_failure_count": manifest.get("accepted_exception_failure_count"),
        "output_root": manifest.get("output_root"),
        "output_path": rel(output_path, repo_root),
        "output_exists": output_path.exists(),
        "manifest_output_hash": output_hash,
        "actual_output_hash": actual_hash,
        "output_row": {
            "market": first_output.get("market"),
            "year": first_output.get("year"),
            "status": first_output.get("status"),
            "vendor_trusted_ohlcv_no_trade_status": first_output.get(
                "vendor_trusted_ohlcv_no_trade_status"
            ),
            "local_trade_gap_gate_status": first_output.get("local_trade_gap_gate_status"),
        },
    }, None


def _stop_conditions() -> list[str]:
    return [
        "Do not execute until this downstream label gate is explicitly approved.",
        "Stop before execution if any expected label artifact already exists.",
        "Stop on external timeout, Python traceback, nonzero exit, manifest-gate failure, missing ES 2026 input, placeholder/provisional cost failure, or output/report path outside the candidate label roots.",
        "Stop if Phase 3 writes anything other than the expected ES 2026 label parquet, label_manifest.json, and label_report.json.",
        "Stop if the label manifest is not PASS for exactly ES 2026 using the candidate causal root and approved causal-base manifest.",
        "Do not run feature matrices, WFA/modeling, metrics, predictions, proof scans, provider actions, staging, commit, push, or live/paper execution from this gate.",
    ]


def _validation_checks(*, output_root: Path, reports_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": "phase3_label_process_result",
            "expected": "exit code 0 before external timeout",
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "detail": "Stop on timeout, Python traceback, nonzero exit, manifest-gate failure, or cost/config failure.",
        },
        {
            "name": "expected_label_artifacts_exist_and_nonempty",
            "expected": _expected_label_artifacts(output_root=output_root, reports_root=reports_root),
            "detail": "Exactly the planned ES 2026 label parquet and label reports should be created.",
        },
        {
            "name": "label_manifest_exact_scope_pass",
            "expected": {
                "path": (reports_root / "label_manifest.json").as_posix(),
                "stage": "labels",
                "status": "PASS",
                "profile": TARGET_PROFILE,
                "resolved_profile": TARGET_PROFILE,
                "markets": [TARGET_MARKET],
                "years": [TARGET_YEAR],
                "input_selection.selected_input_count": 1,
                "causal_base_manifest_gate.passed": True,
            },
            "detail": "The generated label manifest must remain exact ES 2026 and trace to the candidate causal manifest.",
        },
        {
            "name": "generated_artifacts_unstaged",
            "command": "git diff --cached --name-only -- data reports",
            "expected": [],
            "detail": "Generated data/** and reports/** artifacts must remain unstaged after any approved label run.",
        },
    ]


def _recommended_next(status: str, *, failed_check_names: Iterable[str] = ()) -> str:
    failed_names = set(failed_check_names)
    if status == STATUS_NO_GO:
        if "phase3_accepted_warning_handling_wired" in failed_names:
            return (
                "Wire approved ES 2026 accepted-warning evidence through the Phase 3 label "
                "command and validation tests, then rerun this console-only gate."
            )
        return "Resolve failed ES 2026 downstream label gate preconditions, then rerun this console-only gate."
    return (
        "Review and approve the bounded ES 2026 Phase 3 label command, or leave it pending; "
        "do not run labels/features without explicit approval."
    )


def build_report(
    *,
    repo_root: Path,
    candidate_causal_root: Path,
    label_output_root: Path,
    label_reports_root: Path,
    build_reports_root: Path,
    profile_config: Path,
    costs_config: Path,
    label_script: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
    gap_review_report: Mapping[str, Any] | None = None,
    manifest_evidence: Mapping[str, Any] | None = None,
    profile_scope_evidence: Mapping[str, Any] | None = None,
    cost_evidence: Mapping[str, Any] | None = None,
    accepted_packet_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    causal_manifest = build_reports_root / "causal_base_manifest.json"
    gap_report = gap_review_report or gap_review.build_report(
        repo_root=repo_root,
        build_reports_root=build_reports_root,
        output_root=candidate_causal_root,
        profile_config=profile_config,
        staged_generated_paths=staged_paths,
    )
    gap_summary = _summary(gap_report)
    manifest = dict(
        manifest_evidence
        if manifest_evidence is not None
        else _manifest_evidence(
            repo_root=repo_root,
            manifest_path=causal_manifest,
            expected_output_root=candidate_causal_root,
        )[0]
    )
    profile_scope = dict(
        profile_scope_evidence
        if profile_scope_evidence is not None
        else _profile_scope_ok(profile_config)
    )
    cost = dict(cost_evidence if cost_evidence is not None else _cost_evidence(costs_config))
    accepted_packet = dict(
        accepted_packet_evidence
        if accepted_packet_evidence is not None
        else _accepted_warning_packet_evidence(profile_config)
    )
    label_flags = _declared_cli_flags(label_script) if label_script.exists() else set()
    command_candidate_causal_root = command_path(candidate_causal_root, repo_root)
    command_label_output_root = command_path(label_output_root, repo_root)
    command_label_reports_root = command_path(label_reports_root, repo_root)
    command_causal_manifest = command_path(causal_manifest, repo_root)
    command_profile_config = command_path(profile_config, repo_root)
    command_costs_config = command_path(costs_config, repo_root)
    label_command = _label_command(
        input_root=command_candidate_causal_root,
        output_root=command_label_output_root,
        reports_root=command_label_reports_root,
        causal_base_manifest=command_causal_manifest,
        profile_config=command_profile_config,
        costs_config=command_costs_config,
        accepted_readiness_exceptions=command_profile_config,
    )
    command_failures = _command_failures(
        label_command,
        input_root=command_candidate_causal_root,
        output_root=command_label_output_root,
        reports_root=command_label_reports_root,
        causal_base_manifest=command_causal_manifest,
        profile_config=command_profile_config,
        costs_config=command_costs_config,
        accepted_readiness_exceptions=command_profile_config,
    )
    accepted_exception_count = _int_count(manifest.get("accepted_exception_count"))
    accepted_exception_failure_count = _int_count(manifest.get("accepted_exception_failure_count"))
    command_argv = shlex.split(label_command)
    command_accepted_path = _arg_value(command_argv, "--accepted-readiness-exceptions")
    expected_artifacts = _expected_label_artifacts(
        output_root=label_output_root,
        reports_root=label_reports_root,
    )
    expected_paths = [resolve_path(repo_root, artifact) for artifact in expected_artifacts]
    expected_rel_paths = [rel(path, repo_root) for path in expected_paths]
    ignored_expected_paths = (
        sorted(
            path
            for path in expected_rel_paths
            if _normalize(path) in {_normalize(item) for item in ignored_generated_paths}
        )
        if ignored_generated_paths is not None
        else _git_ignored_paths(repo_root, expected_rel_paths)
    )
    unignored_expected_paths = sorted(set(expected_rel_paths) - set(ignored_expected_paths))
    existing_expected_paths = sorted(rel(path, repo_root) for path in expected_paths if path.exists())

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="gap_gate_review_ready_aligned",
        passed=(
            gap_summary.get("status") == gap_review.STATUS_READY
            and gap_summary.get("postcondition_alignment_status") == "ALIGNED"
        ),
        observed={
            "status": gap_summary.get("status"),
            "postcondition_alignment_status": gap_summary.get("postcondition_alignment_status"),
        },
        expected="review-ready aligned ES 2026 gap-gate postcondition",
        detail="Downstream use must start from the reviewed candidate causal-base postcondition.",
    )
    _check(
        checks,
        name="candidate_causal_manifest_exact_es2026_pass",
        passed=(
            manifest.get("status") == "PASS"
            and manifest.get("manifest_status") == "PASS"
            and manifest.get("stage") == "causal_base"
            and manifest.get("profile") == TARGET_PROFILE
            and manifest.get("processed_market_year_count") == 1
            and manifest.get("processed_market_years")
            == [{"market": TARGET_MARKET, "year": TARGET_YEAR}]
            and manifest.get("accepted_exception_count") == 1
            and manifest.get("accepted_exception_failure_count") == 0
            and manifest.get("output_exists") is True
            and manifest.get("manifest_output_hash") == manifest.get("actual_output_hash")
        ),
        observed=manifest,
        expected="PASS causal manifest for exactly ES 2026 with matching output hash",
        detail="The label gate must trace to the exact approved candidate causal output.",
    )
    _check(
        checks,
        name="profile_config_contains_es2026_forward_scope",
        passed=profile_scope.get("status") == "PASS",
        observed=profile_scope,
        expected="tier_3_forward includes ES 2026",
        detail="The bounded label command must remain inside the configured profile scope.",
    )
    _check(
        checks,
        name="cost_config_covers_es",
        passed=(
            cost.get("status") == "PASS"
            and cost.get("tick_size") is not None
            and cost.get("tick_value") is not None
            and cost.get("point_value") is not None
            and cost.get("provisional") is False
        ),
        observed=cost,
        expected="non-provisional ES cost config with tick size/value and point value",
        detail="Phase 3 labels require explicit cost assumptions before generating targets.",
    )
    _check(
        checks,
        name="profile_config_contains_approved_es2026_warning_packet",
        passed=accepted_packet.get("status") == "PASS",
        observed=accepted_packet,
        expected={
            "profile": TARGET_PROFILE,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "category": EXPECTED_ACCEPTED_EXCEPTION_CATEGORY,
            "warning": EXPECTED_ACCEPTED_WARNING,
        },
        detail="The approval command may only pass the exact reviewed ES 2026 accepted-warning packet.",
    )
    _check(
        checks,
        name="phase3_label_cli_has_bounded_controls",
        passed=REQUIRED_LABEL_FLAGS <= label_flags,
        observed=sorted(label_flags),
        expected=sorted(REQUIRED_LABEL_FLAGS),
        detail="The Phase 3 command must support bounded market/year filters and explicit manifest/config paths.",
    )
    _check(
        checks,
        name="phase3_label_command_exact_and_bounded",
        passed=not command_failures,
        observed=command_failures,
        expected="exact ES 2026 Phase 3 label command with bounded accepted-readiness evidence",
        detail="The approval packet must expose one exact bounded label command.",
    )
    _check(
        checks,
        name="phase3_accepted_warning_handling_wired",
        passed=(
            accepted_exception_count == 0
            or (
                accepted_exception_count == 1
                and accepted_exception_failure_count == 0
                and command_accepted_path == command_profile_config.as_posix()
                and accepted_packet.get("status") == "PASS"
            )
        ),
        observed={
            "causal_base_manifest_accepted_exception_count": accepted_exception_count,
            "causal_base_manifest_accepted_exception_failure_count": accepted_exception_failure_count,
            "phase3_command_accepted_readiness_exceptions": command_accepted_path,
            "expected_accepted_readiness_exceptions": command_profile_config.as_posix(),
            "compatible_es2026_accepted_warning_handling": (
                command_accepted_path == command_profile_config.as_posix()
                and accepted_packet.get("status") == "PASS"
            ),
        },
        expected=(
            "zero upstream accepted exceptions, or an explicitly wired and validated "
            "ES 2026 Phase 3 accepted-warning evidence path"
        ),
        detail=(
            "The ES 2026 candidate causal manifest carries an accepted upstream warning. "
            "Current Phase 3 label execution rejects warning-bearing causal manifests unless "
            "accepted-warning evidence is passed through a compatible label command, so this "
            "gate fails closed instead of exposing a known-failing approval command."
        ),
    )
    _check(
        checks,
        name="expected_label_artifacts_ignored_by_git",
        passed=not unignored_expected_paths and len(ignored_expected_paths) == len(expected_rel_paths),
        observed=unignored_expected_paths,
        expected=[],
        detail="All planned label outputs must be ignored generated artifacts before execution.",
    )
    _check(
        checks,
        name="expected_label_artifacts_absent_before_execution",
        passed=not existing_expected_paths,
        observed=existing_expected_paths,
        expected=[],
        detail="The gate must not overwrite an existing ES 2026 label artifact.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while proposing labels.",
    )
    _check(
        checks,
        name="downstream_label_gate_console_only_default",
        passed=True,
        observed="no output writer and no subprocess execution",
        expected="gate only",
        detail="This gate writes no reports, creates no labels, and runs no build command.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_READY
    approval_gate = {
        "approval_required": True,
        "approval_token": "APPROVE_ES2026_P1_PHASE3_LABEL_BUILD_V1",
        "command_family": "phase3_label_build_exact_es2026_candidate",
        "exact_command": label_command,
        "maximum_scope": {
            "market_years": [{"market": TARGET_MARKET, "year": TARGET_YEAR}],
            "profile": TARGET_PROFILE,
            "input_root": rel(candidate_causal_root, repo_root),
            "output_root": rel(label_output_root, repo_root),
            "reports_root": rel(label_reports_root, repo_root),
            "causal_base_manifest": rel(causal_manifest, repo_root),
            "network": False,
            "canonical_data_mutation": False,
        },
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "expected_ignored_artifacts": expected_rel_paths,
        "validation_checks_after_execution": _validation_checks(
            output_root=label_output_root,
            reports_root=label_reports_root,
        ),
        "forbidden_actions_without_separate_approval": list(FORBIDDEN_ACTIONS),
        "stop_conditions": _stop_conditions(),
    }
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_GATE_ONLY,
            "market": TARGET_MARKET,
            "year": TARGET_YEAR,
            "profile": TARGET_PROFILE,
            "gap_gate_review_status": gap_summary.get("status"),
            "gap_gate_postcondition_alignment_status": gap_summary.get(
                "postcondition_alignment_status"
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
            "recommended_next_action": _recommended_next(
                status,
                failed_check_names=(str(check.get("name")) for check in failures),
            ),
            **_approval_flags(),
        },
        "checks": checks,
        "approval_gate": {} if failures else approval_gate,
        "source_evidence": {
            "gap_gate_review": gap_review.review_packet(gap_report),
            "candidate_causal_manifest": manifest,
            "profile_scope": profile_scope,
            "cost_config": cost,
            "accepted_warning_packet": accepted_packet,
            "phase3_label_cli_flags": sorted(label_flags),
        },
        "expected_generated_artifacts": expected_rel_paths,
        "unignored_expected_generated_artifacts": unignored_expected_paths,
        "existing_expected_generated_artifacts": existing_expected_paths,
        "non_approval": {
            "scope": "ES 2026 downstream label approval gate only",
            "generated_report_written": False,
            "generated_output_count": 0,
            "commands_executed": 0,
            **_approval_flags(),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--candidate-causal-root", default=str(DEFAULT_CANDIDATE_CAUSAL_ROOT))
    parser.add_argument("--label-output-root", default=str(DEFAULT_LABEL_OUTPUT_ROOT))
    parser.add_argument("--label-reports-root", default=str(DEFAULT_LABEL_REPORTS_ROOT))
    parser.add_argument("--build-reports-root", default=str(DEFAULT_BUILD_REPORTS_ROOT))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--costs-config", default=str(DEFAULT_COSTS_CONFIG))
    parser.add_argument("--label-script", default=str(DEFAULT_LABEL_SCRIPT))
    parser.add_argument("--print-gate-json", action="store_true")
    return parser


def gate_packet(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "stage": STAGE,
        "status": summary.get("status"),
        "market": summary.get("market"),
        "year": summary.get("year"),
        "profile": summary.get("profile"),
        "approval_gate": report.get("approval_gate", {}),
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
            candidate_causal_root=resolve_path(repo_root, args.candidate_causal_root),
            label_output_root=resolve_path(repo_root, args.label_output_root),
            label_reports_root=resolve_path(repo_root, args.label_reports_root),
            build_reports_root=resolve_path(repo_root, args.build_reports_root),
            profile_config=resolve_path(repo_root, args.profile_config),
            costs_config=resolve_path(repo_root, args.costs_config),
            label_script=resolve_path(repo_root, args.label_script),
        )
    except Exception as exc:
        print(f"{STAGE} status={STATUS_NO_GO} error={type(exc).__name__}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} status={summary['status']} "
        f"gap_gate_review_status={summary['gap_gate_review_status']} "
        f"gap_gate_postcondition_alignment_status={summary['gap_gate_postcondition_alignment_status']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"ignored_expected_generated_outputs={summary['ignored_expected_generated_output_count']} "
        f"unignored_expected_generated_outputs={summary['unignored_expected_generated_output_count']} "
        f"existing_expected_generated_outputs={summary['existing_expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"commands_executed={summary['commands_executed']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    if args.print_gate_json:
        print(json.dumps(gate_packet(report), sort_keys=True))
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
