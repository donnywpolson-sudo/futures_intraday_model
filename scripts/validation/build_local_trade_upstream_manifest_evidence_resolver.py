#!/usr/bin/env python3
"""Classify upstream manifest evidence blockers before local-trade labels."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_baseline_readiness as readiness_gate


STAGE = "local_trade_upstream_manifest_evidence_resolver"
STATUS_PLAN_READY = "UPSTREAM_MANIFEST_EVIDENCE_RESOLUTION_PLAN_READY"
STATUS_NO_GO = "NO_GO_UPSTREAM_MANIFEST_EVIDENCE_RESOLUTION"
DECISION_PLAN_ONLY = "upstream_manifest_evidence_resolution_plan_only"
DECISION_BLOCKED = "upstream_manifest_evidence_resolution_blocked"

CLASS_CANDIDATE_PROJECTION = "CANDIDATE_PROFILE_PROJECTION_FEASIBLE_APPROVAL_REQUIRED"
CLASS_REPAIRED_WARNING = "REPAIRED_ROOT_WARNING_EVIDENCE_REQUIRED"
CLASS_REPAIRED_FAILURE = "REPAIRED_ROOT_FAILURE_EVIDENCE_REQUIRED"
CLASS_REPAIRED_METADATA = "REPAIRED_ROOT_METADATA_EVIDENCE_REQUIRED"
CLASS_EXACT_PASS_READY = "EXACT_PASS_MANIFEST_ALREADY_READY"
CLASS_MANIFEST_MISSING = "MANIFEST_EVIDENCE_MISSING"

FALSE_APPROVAL_FLAGS = (
    "manifest_projection_approved",
    "accepted_warning_approved",
    "causal_base_repair_approved",
) + readiness_gate.FALSE_APPROVAL_FLAGS

DEFAULT_PROPOSAL = readiness_gate.DEFAULT_PROPOSAL
DEFAULT_EXPECTED_ELIGIBLE_MARKETS = readiness_gate.DEFAULT_EXPECTED_ELIGIBLE_MARKETS
DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS = readiness_gate.DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS
ALL_RAW_PROFILE = "all_raw"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return readiness_gate.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return readiness_gate.rel(path, repo_root)


def _read_json_object(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, Mapping) else None


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _messages(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Mapping):
        messages: list[str] = []
        for key, raw_value in value.items():
            if raw_value in (None, True, ""):
                messages.append(str(key))
            else:
                messages.append(f"{key}: {raw_value}")
        return messages
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return []


def _nonempty(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(value)


def _resolve_repo_path(repo_root: Path, value: Any) -> Path | None:
    if value is None:
        return None
    candidate = Path(str(value))
    return candidate if candidate.is_absolute() else repo_root / candidate


def _paths_match(repo_root: Path, left: Any, right: Path) -> bool:
    left_path = _resolve_repo_path(repo_root, left)
    if left_path is None:
        return False
    try:
        return left_path.resolve() == right.resolve()
    except (OSError, ValueError):
        return False


def _manifest_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "reports").glob("**/causal_base_manifest.json"))


def _output_rows(manifest: Mapping[str, Any]) -> dict[tuple[str, int], Mapping[str, Any]]:
    outputs = manifest.get("outputs")
    rows: dict[tuple[str, int], Mapping[str, Any]] = {}
    if not isinstance(outputs, list):
        return rows
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        market = output.get("market")
        year = _int_value(output.get("year"))
        if market is not None and year is not None:
            rows[(str(market), year)] = output
    return rows


def _selected_rows(
    manifest: Mapping[str, Any],
    pairs: Iterable[tuple[str, int]],
) -> tuple[list[Mapping[str, Any]], list[tuple[str, int]]]:
    row_map = _output_rows(manifest)
    selected: list[Mapping[str, Any]] = []
    missing: list[tuple[str, int]] = []
    for pair in sorted({(str(market), int(year)) for market, year in pairs}):
        row = row_map.get(pair)
        if row is None:
            missing.append(pair)
        else:
            selected.append(row)
    return selected, missing


def _row_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market": row.get("market"),
        "year": row.get("year"),
        "status": row.get("status"),
        "warning_count": _int_value(row.get("warning_count")) or 0,
        "failure_count": _int_value(row.get("failure_count")) or 0,
        "warnings": _messages(row.get("warnings")),
        "failures": _messages(row.get("failures")),
    }


def _hash_reference_failures(
    *,
    repo_root: Path,
    manifest: Mapping[str, Any],
    output_root: Path,
    pairs: Iterable[tuple[str, int]],
) -> list[str]:
    output_hashes = manifest.get("output_file_hashes")
    if not isinstance(output_hashes, Mapping):
        return ["output_file_hashes missing or invalid"]

    referenced: dict[Path, Any] = {}
    for raw_path, raw_hash in output_hashes.items():
        resolved = _resolve_repo_path(repo_root, raw_path)
        if resolved is not None:
            referenced[resolved.resolve()] = raw_hash

    failures: list[str] = []
    for market, year in sorted({(str(market), int(year)) for market, year in pairs}):
        expected = (output_root / market / f"{year}.parquet").resolve()
        raw_hash = referenced.get(expected)
        if raw_hash is None:
            failures.append(f"output hash reference missing: {rel(expected, repo_root)}")
        elif str(raw_hash) in {"", "MISSING", "NOT_WRITTEN"}:
            failures.append(f"output hash reference invalid: {rel(expected, repo_root)}")
    return failures


def _manifest_warning_count(manifest: Mapping[str, Any]) -> int:
    warning_count = _int_value(manifest.get("warning_count"))
    if warning_count is not None:
        return warning_count
    summary = manifest.get("summary")
    if isinstance(summary, Mapping):
        summary_count = _int_value(summary.get("warn_count"))
        if summary_count is not None:
            return summary_count
    return 0


def _manifest_failure_count(manifest: Mapping[str, Any]) -> int:
    failure_count = _int_value(manifest.get("failure_count"))
    if failure_count is not None:
        return failure_count
    summary = manifest.get("summary")
    if isinstance(summary, Mapping):
        summary_count = _int_value(summary.get("fail_count"))
        if summary_count is not None:
            return summary_count
    return 0


def _candidate_group(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    manifest_paths: list[Path],
) -> dict[str, Any]:
    causal_root = resolve_path(repo_root, str(group["causal_root"]))
    markets = [str(market) for market in group["markets"]]
    year = int(group["year"])
    pairs = [(market, year) for market in markets]
    inspected = 0
    closest_blockers: list[dict[str, Any]] = []

    for manifest_path in manifest_paths:
        manifest = _read_json_object(manifest_path)
        if manifest is None:
            continue
        if manifest.get("stage") != "causal_base" or not _paths_match(repo_root, manifest.get("output_root"), causal_root):
            continue
        inspected += 1
        selected, missing_rows = _selected_rows(manifest, pairs)
        if missing_rows:
            continue

        blockers: list[str] = []
        if manifest.get("status") != "PASS":
            blockers.append(f"manifest status is {manifest.get('status')!r}, not 'PASS'")
        if manifest.get("profile") != ALL_RAW_PROFILE:
            blockers.append(f"manifest profile is {manifest.get('profile')!r}, not {ALL_RAW_PROFILE!r}")
        if manifest.get("resolved_profile") != ALL_RAW_PROFILE:
            blockers.append(
                f"manifest resolved_profile is {manifest.get('resolved_profile')!r}, not {ALL_RAW_PROFILE!r}"
            )
        if _manifest_failure_count(manifest) != 0 or _nonempty(manifest.get("failures")):
            blockers.append("manifest has failures")
        if _manifest_warning_count(manifest) != 0 or _messages(manifest.get("warnings")):
            blockers.append("manifest has warnings")

        row_blockers: list[str] = []
        for row in selected:
            summary = _row_summary(row)
            if summary["status"] != "PASS":
                row_blockers.append(f"{summary['market']}:{summary['year']} status={summary['status']!r}")
            if summary["warning_count"] or summary["warnings"]:
                row_blockers.append(f"{summary['market']}:{summary['year']} has warnings")
            if summary["failure_count"] or summary["failures"]:
                row_blockers.append(f"{summary['market']}:{summary['year']} has failures")
        blockers.extend(row_blockers)
        blockers.extend(_hash_reference_failures(repo_root=repo_root, manifest=manifest, output_root=causal_root, pairs=pairs))

        if not blockers:
            return {
                "causal_root": rel(causal_root, repo_root),
                "year": year,
                "planned_profile": group.get("profile"),
                "planned_resolved_profile": group.get("resolved_profile"),
                "markets": markets,
                "source_root_classification": "candidate_root",
                "classification": CLASS_CANDIDATE_PROJECTION,
                "manifest_path": rel(manifest_path, repo_root),
                "manifest_profile": manifest.get("profile"),
                "manifest_resolved_profile": manifest.get("resolved_profile"),
                "manifest_status": manifest.get("status"),
                "selected_outputs": [_row_summary(row) for row in selected],
                "approval_required": True,
                "proposed_repair_path": (
                    "Review and approve a bounded manifest-profile projection from the existing PASS "
                    "all_raw candidate-root manifest to the planned Phase 3 profile/year scope; do not "
                    "change parquet data or run labels/features."
                ),
                "blockers": [],
            }
        closest_blockers.append({"manifest_path": rel(manifest_path, repo_root), "blockers": blockers[:6]})

    return {
        "causal_root": rel(causal_root, repo_root),
        "year": year,
        "planned_profile": group.get("profile"),
        "planned_resolved_profile": group.get("resolved_profile"),
        "markets": markets,
        "source_root_classification": "candidate_root",
        "classification": CLASS_MANIFEST_MISSING,
        "manifest_path": None,
        "inspected_manifest_count": inspected,
        "approval_required": True,
        "proposed_repair_path": (
            "Locate or regenerate bounded candidate-root causal-base manifest evidence before any "
            "profile projection, label build, or feature build."
        ),
        "blockers": closest_blockers[:5],
    }


def _matching_repaired_manifests(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    manifest_paths: list[Path],
) -> list[tuple[Path, Mapping[str, Any], list[Mapping[str, Any]]]]:
    causal_root = resolve_path(repo_root, str(group["causal_root"]))
    markets = [str(market) for market in group["markets"]]
    year = int(group["year"])
    pairs = [(market, year) for market in markets]
    matches: list[tuple[Path, Mapping[str, Any], list[Mapping[str, Any]]]] = []
    for manifest_path in manifest_paths:
        manifest = _read_json_object(manifest_path)
        if manifest is None:
            continue
        if manifest.get("stage") != "causal_base":
            continue
        if manifest.get("profile") != group.get("profile"):
            continue
        if not _paths_match(repo_root, manifest.get("output_root"), causal_root):
            continue
        selected, missing = _selected_rows(manifest, pairs)
        if missing:
            continue
        matches.append((manifest_path, manifest, selected))
    return sorted(matches, key=lambda item: rel(item[0], repo_root))


def _repaired_group(
    *,
    repo_root: Path,
    group: Mapping[str, Any],
    manifest_paths: list[Path],
) -> dict[str, Any]:
    causal_root = resolve_path(repo_root, str(group["causal_root"]))
    markets = [str(market) for market in group["markets"]]
    year = int(group["year"])
    pairs = [(market, year) for market in markets]
    matches = _matching_repaired_manifests(repo_root=repo_root, group=group, manifest_paths=manifest_paths)
    if not matches:
        return {
            "causal_root": rel(causal_root, repo_root),
            "year": year,
            "planned_profile": group.get("profile"),
            "planned_resolved_profile": group.get("resolved_profile"),
            "markets": markets,
            "source_root_classification": "repaired_root",
            "classification": CLASS_MANIFEST_MISSING,
            "manifest_path": None,
            "approval_required": True,
            "proposed_repair_path": (
                "Create or locate bounded repaired-root causal-base manifest evidence before any label "
                "or feature build."
            ),
            "blockers": ["no repaired-root manifest covers the selected market-year scope"],
        }

    manifest_path, manifest, selected = matches[0]
    selected_summaries = [_row_summary(row) for row in selected]
    metadata_blockers: list[str] = []
    warning_blockers: list[dict[str, Any]] = []
    failure_blockers: list[str] = []

    planned_resolved = group.get("resolved_profile")
    if planned_resolved is not None and manifest.get("resolved_profile") != planned_resolved:
        metadata_blockers.append(
            f"manifest resolved_profile is {manifest.get('resolved_profile')!r}, not {planned_resolved!r}"
        )
    if manifest.get("status") not in {"PASS", "WARN"}:
        failure_blockers.append(f"manifest status is {manifest.get('status')!r}")
    if _manifest_failure_count(manifest) != 0 or _nonempty(manifest.get("failures")):
        failure_blockers.append("manifest has failures")

    if manifest.get("status") == "WARN" or _manifest_warning_count(manifest) or _messages(manifest.get("warnings")):
        warning_blockers.append(
            {
                "scope": "manifest",
                "status": manifest.get("status"),
                "warning_count": _manifest_warning_count(manifest),
                "warnings": _messages(manifest.get("warnings")),
            }
        )

    for row_summary in selected_summaries:
        market_year = f"{row_summary['market']}:{row_summary['year']}"
        if row_summary["status"] not in {"PASS", "WARN"}:
            failure_blockers.append(f"{market_year} status={row_summary['status']!r}")
        if row_summary["failure_count"] or row_summary["failures"]:
            failure_blockers.append(f"{market_year} has failures")
        if row_summary["status"] == "WARN" or row_summary["warning_count"] or row_summary["warnings"]:
            warning_blockers.append(
                {
                    "scope": market_year,
                    "status": row_summary["status"],
                    "warning_count": row_summary["warning_count"],
                    "warnings": row_summary["warnings"],
                }
            )

    hash_failures = _hash_reference_failures(repo_root=repo_root, manifest=manifest, output_root=causal_root, pairs=pairs)
    metadata_blockers.extend(hash_failures)

    if failure_blockers:
        classification = CLASS_REPAIRED_FAILURE
        proposed_path = (
            "Run only an explicitly approved bounded causal-base repair for the selected repaired-root "
            "market-years, then rerun readiness; do not run labels/features."
        )
    elif warning_blockers:
        classification = CLASS_REPAIRED_WARNING
        proposed_path = (
            "Review the selected warnings and approve either an accepted-warning packet or a bounded "
            "causal-base repair; do not project WARN rows to PASS or run labels/features without approval."
        )
    elif metadata_blockers:
        classification = CLASS_REPAIRED_METADATA
        proposed_path = (
            "Repair manifest metadata or provide accepted evidence for the repaired-root manifest before "
            "any label or feature build."
        )
    else:
        classification = CLASS_EXACT_PASS_READY
        proposed_path = "Rerun baseline readiness; this group appears to have exact PASS manifest evidence."

    return {
        "causal_root": rel(causal_root, repo_root),
        "year": year,
        "planned_profile": group.get("profile"),
        "planned_resolved_profile": group.get("resolved_profile"),
        "markets": markets,
        "source_root_classification": "repaired_root",
        "classification": classification,
        "manifest_path": rel(manifest_path, repo_root),
        "manifest_profile": manifest.get("profile"),
        "manifest_resolved_profile": manifest.get("resolved_profile"),
        "manifest_status": manifest.get("status"),
        "manifest_warning_count": _manifest_warning_count(manifest),
        "selected_outputs": selected_summaries,
        "metadata_blockers": metadata_blockers,
        "warning_blockers": warning_blockers,
        "failure_blockers": failure_blockers,
        "approval_required": classification != CLASS_EXACT_PASS_READY,
        "proposed_repair_path": proposed_path,
    }


def _blocked_groups(baseline_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_failures = baseline_report.get("phase3_causal_base_manifest_failures")
    failures = [row for row in raw_failures if isinstance(row, Mapping)] if isinstance(raw_failures, list) else []
    groups: list[dict[str, Any]] = []
    for failure in failures:
        markets = failure.get("markets")
        if not isinstance(markets, list) or failure.get("year") is None or not failure.get("causal_root"):
            continue
        groups.append(
            {
                "causal_root": str(failure["causal_root"]),
                "profile": failure.get("profile"),
                "resolved_profile": failure.get("resolved_profile"),
                "markets": [str(market) for market in markets],
                "year": int(failure["year"]),
                "baseline_reason": failure.get("reason"),
            }
        )
    return sorted(groups, key=lambda item: (str(item["causal_root"]), int(item["year"])))


def _classify_groups(
    *,
    repo_root: Path,
    baseline_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    manifest_paths = _manifest_paths(repo_root)
    classified: list[dict[str, Any]] = []
    for group in _blocked_groups(baseline_report):
        if group["causal_root"] == ledger_gate.CANDIDATE_CAUSAL_ROOT:
            classified.append(_candidate_group(repo_root=repo_root, group=group, manifest_paths=manifest_paths))
        else:
            classified.append(_repaired_group(repo_root=repo_root, group=group, manifest_paths=manifest_paths))
    return classified


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


def _recommended_next(status: str, class_counts: Counter[str]) -> str:
    if status == STATUS_NO_GO:
        return "Resolve failed resolver preconditions, then rerun the upstream manifest evidence resolver."
    if class_counts.get(CLASS_REPAIRED_WARNING):
        return (
            "Review and approve or reject one bounded upstream evidence repair path: candidate-root "
            "manifest projection where feasible, and accepted-warning packet or bounded causal-base "
            "repair for repaired-root warnings; do not run labels or features."
        )
    if class_counts.get(CLASS_MANIFEST_MISSING):
        return (
            "Locate or create bounded upstream causal-base manifest evidence for missing groups before "
            "any label or feature build."
        )
    if class_counts.get(CLASS_CANDIDATE_PROJECTION):
        return (
            "Review and approve or reject the candidate-root manifest projection path; do not run labels "
            "or features."
        )
    return "Rerun baseline readiness and prepare a bounded label/feature build plan only if it returns review-ready."


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    expected_eligible_market_count: int = DEFAULT_EXPECTED_ELIGIBLE_MARKETS,
    expected_proof_status_market_year_count: int = DEFAULT_EXPECTED_PROOF_STATUS_MARKET_YEARS,
) -> dict[str, Any]:
    baseline_report = readiness_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        staged_generated_paths=staged_generated_paths,
        expected_eligible_market_count=expected_eligible_market_count,
        expected_proof_status_market_year_count=expected_proof_status_market_year_count,
    )
    baseline_summary = baseline_report["summary"]
    groups = _classify_groups(repo_root=repo_root, baseline_report=baseline_report)
    class_counts: Counter[str] = Counter(str(group["classification"]) for group in groups)
    staged_count = int(baseline_summary.get("staged_generated_path_count") or 0)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="baseline_readiness_scope_available",
        passed=baseline_summary.get("status") != readiness_gate.STATUS_NO_GO,
        observed=baseline_summary.get("status"),
        expected=f"not {readiness_gate.STATUS_NO_GO}",
        detail="Resolver can only classify manifest evidence after baseline readiness has no hard failures.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=staged_count == 0,
        observed=staged_count,
        expected=0,
        detail="Generated data/** and reports/** artifacts must not be staged while resolving manifest evidence.",
    )
    _check(
        checks,
        name="phase3_manifest_blockers_classified",
        passed=bool(groups) or baseline_summary.get("status") == readiness_gate.STATUS_READY,
        observed=len(groups),
        expected="blocked groups classified or baseline readiness already review-ready",
        detail="Every Phase 3 manifest blocker from baseline readiness should receive a resolver classification.",
    )
    _check(
        checks,
        name="resolver_console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only by default",
        detail="This gate does not expose generated report output arguments.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_NO_GO if failures else STATUS_PLAN_READY
    decision = DECISION_BLOCKED if failures else DECISION_PLAN_ONLY
    next_action = _recommended_next(status, class_counts)
    approval_flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}

    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": decision,
            "input_proposal": rel(proposal_path, repo_root),
            "input_baseline_readiness_status": baseline_summary.get("status"),
            "blocked_group_count": len(groups),
            "candidate_projection_feasible_count": class_counts.get(CLASS_CANDIDATE_PROJECTION, 0),
            "repaired_warning_evidence_required_count": class_counts.get(CLASS_REPAIRED_WARNING, 0),
            "repaired_failure_evidence_required_count": class_counts.get(CLASS_REPAIRED_FAILURE, 0),
            "repaired_metadata_evidence_required_count": class_counts.get(CLASS_REPAIRED_METADATA, 0),
            "missing_manifest_evidence_count": class_counts.get(CLASS_MANIFEST_MISSING, 0),
            "exact_pass_ready_count": class_counts.get(CLASS_EXACT_PASS_READY, 0),
            "staged_generated_path_count": staged_count,
            "generated_report_written": False,
            "generated_output_count": 0,
            "failure_count": len(failures),
            "recommended_next_action": next_action,
            **approval_flags,
        },
        "checks": checks,
        "groups": groups,
        "classification_counts": dict(sorted(class_counts.items())),
        "baseline_readiness_summary": {
            "status": baseline_summary.get("status"),
            "action_required_count": baseline_summary.get("action_required_count"),
            "failure_count": baseline_summary.get("failure_count"),
            "label_build_command_ready": baseline_summary.get("label_build_command_ready"),
            "feature_matrix_command_ready": baseline_summary.get("feature_matrix_command_ready"),
        },
        "non_approval": {
            "scope": "upstream manifest evidence resolver only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **approval_flags,
        },
    }


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
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"blocked_groups={summary['blocked_group_count']} "
        f"candidate_projection_feasible={summary['candidate_projection_feasible_count']} "
        f"repaired_warning_evidence_required={summary['repaired_warning_evidence_required_count']} "
        f"missing_manifest_evidence={summary['missing_manifest_evidence_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 1 if summary["status"] == STATUS_NO_GO else 0


if __name__ == "__main__":
    raise SystemExit(main())
