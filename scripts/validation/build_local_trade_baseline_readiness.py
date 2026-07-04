#!/usr/bin/env python3
"""Assess baseline readiness for local-trade model-eligible markets."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_model_eligible_scope as scope_gate
from scripts.pipeline_gates import check_upstream_manifest
from scripts.profile_scope import load_profile_scope


STAGE = "local_trade_baseline_readiness"
STATUS_READY = "REVIEW_READY_LOCAL_TRADE_BASELINE_READINESS"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED_LOCAL_TRADE_BASELINE_READINESS"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_BASELINE_READINESS"
DECISION_READY = "baseline_readiness_defined_no_build_execution"
DECISION_ACTION_REQUIRED = "baseline_readiness_requires_source_only_controls"
DECISION_BLOCKED = "baseline_readiness_blocked"

DEFAULT_PROPOSAL = scope_gate.DEFAULT_PROPOSAL
DEFAULT_LABEL_SCRIPT = Path("scripts/phase3_labels/build_labels.py")
DEFAULT_FEATURE_SCRIPT = Path("scripts/phase4_features/build_baseline_features.py")
DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_EXPECTED_ELIGIBLE_MARKETS = 7
DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS = 14
YEAR_PROFILE_COMMANDS = {
    2025: "tier_3_holdout",
    2026: "tier_3_forward",
}
DEFAULT_LABEL_OUTPUT_ROOT = "data/labeled"
DEFAULT_FEATURE_OUTPUT_ROOT = "data/feature_matrices/baseline"

FALSE_APPROVAL_FLAGS = (
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "canonical_promotion_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return ledger_gate.rel(path, repo_root)


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    failure_status: str = "FAIL",
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else failure_status,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _read_yaml(path: Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, Mapping) else {}


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


def _configured_cost_markets(costs_config: Path) -> set[str]:
    if not costs_config.exists():
        return set()
    payload = _read_yaml(costs_config)
    markets = payload.get("markets")
    if not isinstance(markets, Mapping):
        return set()
    return {str(market) for market in markets}


def _profile_scope(profile_config: Path, profile_name: str) -> tuple[set[str], set[int]]:
    if not profile_config.exists():
        return set(), set()
    payload = _read_yaml(profile_config)
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        return set(), set()
    profile = profiles.get(profile_name)
    if not isinstance(profile, Mapping):
        return set(), set()
    markets = profile.get("markets")
    years = profile.get("years")
    market_set = {str(market) for market in markets} if isinstance(markets, list) else set()
    year_set = {int(year) for year in years} if isinstance(years, list) else set()
    return market_set, year_set


def _eligible_market_scope(scope_report: Mapping[str, Any]) -> tuple[list[str], list[int], list[dict[str, Any]]]:
    eligible_rows = scope_report.get("model_eligible_markets")
    rows = [row for row in eligible_rows if isinstance(row, dict)] if isinstance(eligible_rows, list) else []
    markets = sorted({str(row.get("market")) for row in rows if row.get("market")})
    years = sorted(
        {
            int(year)
            for row in rows
            for year in (row.get("proof_status_years") if isinstance(row.get("proof_status_years"), list) else [])
        }
    )
    return markets, years, rows


def _eligible_market_year_count(eligible_rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(
        len(row.get("proof_status_years", []))
        for row in eligible_rows
        if isinstance(row.get("proof_status_years"), list)
    )


def _missing_year_profiles(years: Iterable[int]) -> list[int]:
    return [year for year in years if year not in YEAR_PROFILE_COMMANDS]


def _profile_coverage_failures(
    *,
    profile_config: Path,
    markets: list[str],
    years: list[int],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    market_set = set(markets)
    for year in years:
        profile = YEAR_PROFILE_COMMANDS.get(year)
        if profile is None:
            failures.append({"year": year, "reason": "no configured command profile"})
            continue
        profile_markets, profile_years = _profile_scope(profile_config, profile)
        missing_markets = sorted(market_set - profile_markets)
        missing_year = year not in profile_years
        if missing_markets or missing_year:
            failures.append(
                {
                    "year": year,
                    "profile": profile,
                    "missing_markets": missing_markets,
                    "missing_year": year if missing_year else None,
                }
            )
    return failures


def _resolve_repo_path(repo_root: Path, value: Any) -> Path | None:
    if value is None:
        return None
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else repo_root / candidate


def _paths_equivalent(repo_root: Path, left: Any, right: Path) -> bool:
    left_path = _resolve_repo_path(repo_root, left)
    if left_path is None:
        return False
    try:
        return left_path.resolve() == right.resolve()
    except (OSError, ValueError):
        return False


def _read_json_object(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, Mapping) else None


def _manifest_prefilter_passes(
    *,
    repo_root: Path,
    manifest_path: Path,
    profile: str,
    resolved_profile: str | None,
    output_root: Path,
    pairs: list[tuple[str, int]],
) -> bool:
    payload = _read_json_object(manifest_path)
    if payload is None:
        return False
    if payload.get("stage") != "causal_base" or payload.get("status") != "PASS":
        return False
    if payload.get("profile") != profile:
        return False
    if resolved_profile is not None and payload.get("resolved_profile") != resolved_profile:
        return False
    if not _paths_equivalent(repo_root, payload.get("output_root"), output_root):
        return False

    outputs = payload.get("outputs")
    output_pairs = (
        {
            (str(output.get("market")), int(output.get("year")))
            for output in outputs
            if isinstance(output, Mapping) and output.get("market") and output.get("year") is not None
        }
        if isinstance(outputs, list)
        else set()
    )
    if any(pair not in output_pairs for pair in pairs):
        return False

    output_hashes = payload.get("output_file_hashes")
    if not isinstance(output_hashes, Mapping):
        return False
    expected_paths = {
        (output_root / market / f"{year}.parquet").resolve()
        for market, year in pairs
    }
    hashed_paths: set[Path] = set()
    for raw_path in output_hashes:
        resolved = _resolve_repo_path(repo_root, raw_path)
        if resolved is not None:
            hashed_paths.add(resolved.resolve())
    return expected_paths <= hashed_paths


def _phase3_manifest_evidence(
    *,
    repo_root: Path,
    profile_config: Path,
    causal_root_groups: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    manifest_paths = sorted((repo_root / "reports").glob("**/causal_base_manifest.json"))
    for group in causal_root_groups:
        causal_root = resolve_path(repo_root, str(group["causal_root"]))
        markets = [str(market) for market in group["markets"]]
        years = [int(year) for year in group["years"]]
        for year in years:
            profile = YEAR_PROFILE_COMMANDS.get(year)
            if profile is None:
                failures.append(
                    {
                        "causal_root": rel(causal_root, repo_root),
                        "year": year,
                        "reason": "no configured year profile",
                    }
                )
                continue
            scope = load_profile_scope(profile, profile_config, strict=False)
            resolved_profile = scope.resolved_profile if scope is not None else None
            pairs = [(market, year) for market in markets]
            prefiltered = [
                path
                for path in manifest_paths
                if _manifest_prefilter_passes(
                    repo_root=repo_root,
                    manifest_path=path,
                    profile=profile,
                    resolved_profile=resolved_profile,
                    output_root=causal_root,
                    pairs=pairs,
                )
            ]
            passed_manifest: Path | None = None
            gate_failures: list[str] = []
            for manifest_path in prefiltered:
                check = check_upstream_manifest(
                    manifest_path=manifest_path,
                    expected_stage="causal_base",
                    expected_profile=profile,
                    expected_resolved_profile=resolved_profile,
                    expected_output_root=causal_root,
                    expected_market_years=pairs,
                    gate_name="baseline_readiness_phase3_causal_base_manifest_gate",
                )
                if check.passed:
                    passed_manifest = manifest_path
                    break
                gate_failures.extend(check.failures)
            if passed_manifest is None:
                failures.append(
                    {
                        "causal_root": rel(causal_root, repo_root),
                        "profile": profile,
                        "resolved_profile": resolved_profile,
                        "markets": markets,
                        "year": year,
                        "prefiltered_candidate_count": len(prefiltered),
                        "reason": "no matching PASS causal_base_manifest for Phase 3 label command",
                        "gate_failures": gate_failures[:5],
                    }
                )
            else:
                evidence.append(
                    {
                        "causal_root": rel(causal_root, repo_root),
                        "profile": profile,
                        "resolved_profile": resolved_profile,
                        "markets": markets,
                        "year": year,
                        "manifest_path": rel(passed_manifest, repo_root),
                    }
                )
    return evidence, failures


def _causal_root_groups(eligible_rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, dict[str, set[Any]]] = {}
    failures: list[dict[str, Any]] = []
    for row in eligible_rows:
        market = row.get("market")
        row_years = row.get("proof_status_years")
        roots = row.get("causal_roots")
        if not market or not isinstance(row_years, list) or not isinstance(roots, list) or len(roots) != 1:
            failures.append(
                {
                    "market": market,
                    "proof_status_years": row_years,
                    "causal_roots": roots,
                }
            )
            continue
        root = str(roots[0])
        entry = grouped.setdefault(root, {"markets": set(), "years": set()})
        entry["markets"].add(str(market))
        entry["years"].update(int(year) for year in row_years)

    groups = [
        {
            "causal_root": root,
            "markets": sorted(str(market) for market in values["markets"]),
            "years": sorted(int(year) for year in values["years"]),
        }
        for root, values in sorted(grouped.items())
    ]
    return groups, failures


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()


def _command_families(
    *,
    markets: list[str],
    years: list[int],
    causal_root_groups: list[dict[str, Any]],
) -> dict[str, list[str]]:
    label_commands: list[str] = []
    for group in causal_root_groups:
        group_markets = ",".join(str(market) for market in group["markets"])
        causal_root = str(group["causal_root"])
        for year in group["years"]:
            profile = YEAR_PROFILE_COMMANDS.get(int(year))
            if profile is None:
                continue
            report_slug = f"{_slug(causal_root)}_{year}"
            label_commands.append(
                "python -m scripts.phase3_labels.build_labels "
                f"--profile {profile} --input-root {causal_root} "
                f"--output-root {DEFAULT_LABEL_OUTPUT_ROOT} "
                f"--reports-root reports/labels/local_trade_baseline/{report_slug} "
                f"--markets {group_markets} --years {year}"
            )

    markets_csv = ",".join(markets)
    feature_commands: list[str] = []
    for year in years:
        profile = YEAR_PROFILE_COMMANDS.get(year)
        if profile is None:
            continue
        feature_commands.append(
            "python -m scripts.phase4_features.build_baseline_features "
            f"--profile {profile} --input-root {DEFAULT_LABEL_OUTPUT_ROOT} "
            f"--output-root {DEFAULT_FEATURE_OUTPUT_ROOT} "
            f"--reports-root reports/features_baseline/local_trade_baseline/{year} "
            f"--markets {markets_csv} --years {year}"
        )
    return {
        "label_build_commands_after_phase3_bounded_controls": label_commands,
        "feature_matrix_build_commands_after_labels": feature_commands,
    }


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
) -> dict[str, Any]:
    scope_report = scope_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        staged_generated_paths=staged_generated_paths,
    )
    scope_summary = scope_report["summary"]
    markets, years, eligible_rows = _eligible_market_scope(scope_report)
    eligible_market_year_count = _eligible_market_year_count(eligible_rows)
    blocked_rows = scope_report.get("blocked_canonical_markets")
    blocked_count = len(blocked_rows) if isinstance(blocked_rows, list) else 0
    staged_paths = sorted(staged_generated_paths) if staged_generated_paths is not None else []
    scope_staged_count = int(scope_summary.get("staged_generated_path_count") or 0)
    staged_path_count = max(len(staged_paths), scope_staged_count)

    label_script = repo_root / DEFAULT_LABEL_SCRIPT
    feature_script = repo_root / DEFAULT_FEATURE_SCRIPT
    profile_config = repo_root / DEFAULT_PROFILE_CONFIG
    costs_config = repo_root / DEFAULT_COSTS_CONFIG
    label_flags = _declared_cli_flags(label_script) if label_script.exists() else set()
    feature_flags = _declared_cli_flags(feature_script) if feature_script.exists() else set()
    cost_markets = _configured_cost_markets(costs_config)
    missing_cost_markets = sorted(set(markets) - cost_markets)
    missing_profiles = _missing_year_profiles(years)
    profile_failures = _profile_coverage_failures(profile_config=profile_config, markets=markets, years=years)
    causal_root_groups, causal_root_failures = _causal_root_groups(eligible_rows)
    phase3_manifest_evidence, phase3_manifest_failures = _phase3_manifest_evidence(
        repo_root=repo_root,
        profile_config=profile_config,
        causal_root_groups=causal_root_groups,
    )
    label_filters_ready = {"--markets", "--years"}.issubset(label_flags)
    feature_filters_ready = {"--markets", "--years"}.issubset(feature_flags)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="model_eligible_scope_ready",
        passed=scope_summary.get("status") == scope_gate.STATUS_READY,
        observed=scope_summary.get("status"),
        expected=scope_gate.STATUS_READY,
        detail="Baseline readiness can only be assessed from a ready model-eligible scope.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_path_count == 0,
        observed=staged_paths if staged_paths else scope_staged_count,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while assessing readiness.",
    )
    _check(
        checks,
        name="eligible_market_count_matches_expected",
        passed=len(markets) == expected_eligible_market_count,
        observed=len(markets),
        expected=expected_eligible_market_count,
        detail="The readiness gate is scoped to the model-eligible markets from proof-status promotion.",
    )
    _check(
        checks,
        name="eligible_proof_status_market_year_count_matches_expected",
        passed=eligible_market_year_count == expected_proof_status_market_year_count,
        observed=eligible_market_year_count,
        expected=expected_proof_status_market_year_count,
        detail="The readiness gate must preserve the promoted proof-status market-year scope.",
    )
    _check(
        checks,
        name="required_source_scripts_present",
        passed=label_script.exists() and feature_script.exists(),
        observed={
            rel(label_script, repo_root): label_script.exists(),
            rel(feature_script, repo_root): feature_script.exists(),
        },
        expected="label and baseline feature scripts exist",
        detail="Readiness requires tracked Phase 3 and Phase 4 source entrypoints.",
    )
    _check(
        checks,
        name="required_configs_present",
        passed=profile_config.exists() and costs_config.exists(),
        observed={
            rel(profile_config, repo_root): profile_config.exists(),
            rel(costs_config, repo_root): costs_config.exists(),
        },
        expected="profile and cost configs exist",
        detail="Readiness requires existing profile and execution-cost configuration.",
    )
    _check(
        checks,
        name="costs_config_covers_eligible_markets",
        passed=not missing_cost_markets and bool(markets),
        observed=missing_cost_markets,
        expected=[],
        detail="Every model-eligible market needs an execution-cost entry before labels/features/modeling.",
    )
    _check(
        checks,
        name="profile_config_covers_eligible_year_profiles",
        passed=not missing_profiles and not profile_failures and bool(years),
        observed={"missing_year_profiles": missing_profiles, "profile_failures": profile_failures},
        expected="tier_3 holdout/forward profiles cover eligible 2025/2026 markets",
        detail="The existing profile config must contain full-universe holdout/forward scopes for bounded commands.",
    )
    _check(
        checks,
        name="eligible_rows_have_single_causal_root",
        passed=not causal_root_failures and bool(causal_root_groups),
        observed=causal_root_failures,
        expected="one causal root per eligible market row",
        detail="Phase 3 label commands require explicit input roots and must be grouped by causal root.",
    )
    _check(
        checks,
        name="phase3_causal_base_manifests_ready",
        passed=not phase3_manifest_failures and bool(phase3_manifest_evidence),
        observed=phase3_manifest_failures,
        expected="matching PASS causal_base_manifest evidence for each Phase 3 label command",
        detail="Each bounded Phase 3 label command must have exact upstream manifest evidence before execution.",
        failure_status="ACTION_REQUIRED",
    )
    _check(
        checks,
        name="phase3_label_cli_bounded_filters",
        passed=label_filters_ready,
        observed=sorted(label_flags),
        expected=["--markets", "--years"],
        detail="Phase 3 labels need bounded market/year filters before any eligible-scope label build is safe.",
        failure_status="ACTION_REQUIRED",
    )
    _check(
        checks,
        name="phase4_feature_cli_bounded_filters",
        passed=feature_filters_ready,
        observed=sorted(feature_flags),
        expected=["--markets", "--years"],
        detail="Phase 4 baseline features must support bounded market/year filters.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    actions_required = [check for check in checks if check["status"] == "ACTION_REQUIRED"]
    if failures:
        status = STATUS_NO_GO
        decision = DECISION_BLOCKED
        next_action = "Resolve failed readiness checks, then rerun the baseline readiness gate."
    elif actions_required:
        status = STATUS_ACTION_REQUIRED
        decision = DECISION_ACTION_REQUIRED
        action_names = {str(check["name"]) for check in actions_required}
        if "phase3_causal_base_manifests_ready" in action_names:
            next_action = (
                "Resolve missing or stale PASS causal-base manifest evidence for the bounded Phase 3 "
                "label commands, then rerun this readiness gate; do not generate labels or features."
            )
        else:
            next_action = (
                "Implement tracked source/tests/docs-only Phase 3 --markets/--years controls for the "
                "model-eligible market-years, then rerun this readiness gate; do not generate labels."
            )
    else:
        status = STATUS_READY
        decision = DECISION_READY
        next_action = (
            "Prepare one bounded label/feature build plan using the reported command families; "
            "do not run generated-artifact builds without explicit approval."
        )

    command_families = _command_families(
        markets=markets,
        years=years,
        causal_root_groups=causal_root_groups,
    )
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "input_proposal": rel(proposal_path, repo_root),
            "input_model_scope_status": scope_summary.get("status"),
            "eligible_market_count": len(markets),
            "eligible_proof_status_market_year_count": eligible_market_year_count,
            "blocked_canonical_market_count": blocked_count,
            "eligible_causal_root_count": len(causal_root_groups),
            "phase3_causal_base_manifest_ready_count": len(phase3_manifest_evidence),
            "staged_generated_path_count": staged_path_count,
            "label_build_command_ready": label_filters_ready and not failures and not actions_required,
            "feature_matrix_command_ready": feature_filters_ready and not failures and not actions_required,
            "baseline_readiness_scope_defined": not failures,
            "action_required_count": len(actions_required),
            "failure_count": len(failures),
            "recommended_next_action": next_action,
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "live_or_paper_execution_approved": False,
        },
        "checks": checks,
        "model_eligible_markets": markets,
        "model_eligible_years": years,
        "model_eligible_market_rows": eligible_rows,
        "eligible_causal_root_groups": causal_root_groups,
        "phase3_causal_base_manifest_evidence": phase3_manifest_evidence,
        "phase3_causal_base_manifest_failures": phase3_manifest_failures,
        "blocked_canonical_markets": blocked_rows if isinstance(blocked_rows, list) else [],
        "command_families": command_families,
        "non_approval": {
            "scope": "baseline readiness assessment only",
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "live_or_paper_execution_approved": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Local Trade Baseline Readiness",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: baseline readiness assessment only; this does not build labels, features, models, WFA splits, metrics, predictions, or live/paper execution artifacts.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Input proposal: `{summary['input_proposal']}`.",
        f"- Eligible markets: {summary['eligible_market_count']}.",
        f"- Eligible proof-status market-years: {summary['eligible_proof_status_market_year_count']}.",
        f"- Blocked canonical markets: {summary['blocked_canonical_market_count']}.",
        f"- Recommended next action: {summary['recommended_next_action']}",
        "",
        "## Non-Approval Flags",
        "",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")

    lines.extend(["", "## Model-Eligible Scope", ""])
    lines.append(f"- Markets: `{', '.join(report['model_eligible_markets'])}`.")
    lines.append(f"- Years: `{', '.join(str(year) for year in report['model_eligible_years'])}`.")

    lines.extend(["", "## Command Families", ""])
    for name, commands in report["command_families"].items():
        lines.append(f"- `{name}`:")
        if commands:
            for command in commands:
                lines.append(f"  - `{command}`")
        else:
            lines.append("  - None.")

    action_checks = [check for check in report["checks"] if check["status"] == "ACTION_REQUIRED"]
    if action_checks:
        lines.extend(["", "## Action Required", ""])
        for check in action_checks:
            lines.append(f"- `{check['name']}` expected `{check['expected']}`.")

    failed_checks = [check for check in report["checks"] if check["status"] == "FAIL"]
    if failed_checks:
        lines.extend(["", "## Failed Checks", ""])
        for check in failed_checks:
            lines.append(f"- `{check['name']}` observed `{check['observed']}` expected `{check['expected']}`.")
    lines.append("")
    return "\n".join(lines)


def _ensure_reports_output(repo_root: Path, output_path: Path) -> None:
    try:
        output_path.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError as exc:
        raise ValueError(f"output path must be under reports/: {rel(output_path, repo_root)}") from exc


def write_report(report: dict[str, Any], *, repo_root: Path, json_out: Path, markdown_out: Path) -> None:
    _ensure_reports_output(repo_root, json_out)
    _ensure_reports_output(repo_root, markdown_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    parser.add_argument("--expected-eligible-market-count", type=int, default=DEFAULT_EXPECTED_ELIGIBLE_MARKETS)
    parser.add_argument(
        "--expected-proof-status-market-year-count",
        type=int,
        default=DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
    )
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    try:
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            expected_eligible_market_count=args.expected_eligible_market_count,
            expected_proof_status_market_year_count=args.expected_proof_status_market_year_count,
        )
        if bool(args.json_out) != bool(args.markdown_out):
            raise ValueError("--json-out and --markdown-out must be supplied together")
        if args.json_out and args.markdown_out:
            write_report(
                report,
                repo_root=repo_root,
                json_out=resolve_path(repo_root, args.json_out),
                markdown_out=resolve_path(repo_root, args.markdown_out),
            )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"eligible_markets={summary['eligible_market_count']} "
        f"eligible_proof_status_market_years={summary['eligible_proof_status_market_year_count']} "
        f"blocked_canonical_markets={summary['blocked_canonical_market_count']} "
        f"label_build_command_ready={summary['label_build_command_ready']} "
        f"feature_matrix_command_ready={summary['feature_matrix_command_ready']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"action_required_count={summary['action_required_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
