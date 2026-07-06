#!/usr/bin/env python3
"""Project approved candidate-root causal-base manifest metadata."""

from __future__ import annotations

import argparse
import copy
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

from scripts.pipeline_gates import file_sha256
from scripts.profile_scope import load_profile_scope
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_baseline_readiness as readiness_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate


STAGE = "local_trade_candidate_manifest_profile_projection"
STATUS_PROJECTED = "PROJECTED_LOCAL_TRADE_CANDIDATE_MANIFEST_PROFILE"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_CANDIDATE_MANIFEST_PROFILE_PROJECTION"
DECISION_APPROVED = "human_approved_candidate_manifest_profile_projection_only"
DECISION_BLOCKED = "candidate_manifest_profile_projection_blocked"

DEFAULT_PROPOSAL = proposal_gate.DEFAULT_JSON_OUT
DEFAULT_SOURCE_MANIFEST = (
    Path("reports")
    / "pipeline_audit"
    / "causal_proof_candidates"
    / "local_trade_2025_2026_v1"
    / "causal_base_manifest.json"
)
DEFAULT_REPORTS_ROOT = (
    Path("reports") / "pipeline_audit" / "local_trade_candidate_manifest_profile_projection"
)
DEFAULT_APPROVED_MARKETS = ("HO", "NG", "RB")
DEFAULT_APPROVED_YEARS = (2025, 2026)
ALL_RAW_PROFILE = "all_raw"

FALSE_APPROVAL_FLAGS = (
    "accepted_warning_packet_approved",
    "causal_base_repair_approved",
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


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


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


def _proposal_rows(proposal: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = proposal.get("proposal_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _row_pair(row: Mapping[str, Any]) -> tuple[str, int] | None:
    market = row.get("market")
    year = row.get("year")
    try:
        return str(market), int(year)
    except (TypeError, ValueError):
        return None


def _row_pair_label(row: Mapping[str, Any]) -> str:
    pair = _row_pair(row)
    return f"{pair[0]}:{pair[1]}" if pair else f"{row.get('market')}:{row.get('year')}"


def _has_causal_root(row: Mapping[str, Any], causal_root: str) -> bool:
    roots = row.get("causal_roots")
    return isinstance(roots, list) and causal_root in {str(root) for root in roots}


def _has_classification(row: Mapping[str, Any], classification: str) -> bool:
    classifications = row.get("source_classifications")
    return isinstance(classifications, list) and classification in {str(item) for item in classifications}


def _candidate_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _has_causal_root(row, ledger_gate.CANDIDATE_CAUSAL_ROOT)
        and _has_classification(row, "candidate_derived_review_evidence")
    ]


def _repaired_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _has_causal_root(row, ledger_gate.TIER1_CAUSAL_ROOT)]


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_years(value: str) -> list[int]:
    years: list[int] = []
    for item in _parse_csv(value):
        years.append(int(item))
    return years


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


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _messages(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [value] if value else []
    return []


def _output_rows(manifest: Mapping[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    outputs = manifest.get("outputs")
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    if not isinstance(outputs, list):
        return rows
    for output in outputs:
        if not isinstance(output, dict):
            continue
        pair = _row_pair(output)
        if pair is not None:
            rows[pair] = output
    return rows


def _matching_hash(repo_root: Path, hash_map: Any, path: Path) -> tuple[str | None, str | None]:
    if not isinstance(hash_map, Mapping):
        return None, None
    expected = path.resolve()
    for raw_path, raw_hash in hash_map.items():
        resolved = _resolve_repo_path(repo_root, raw_path)
        if resolved is None:
            continue
        try:
            if resolved.resolve() == expected:
                return str(raw_path), str(raw_hash)
        except (OSError, ValueError):
            continue
    return None, None


def _clean_row_failures(row: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    pair = _row_pair_label(row)
    if row.get("status") != "PASS":
        failures.append(f"{pair} status is {row.get('status')!r}, not 'PASS'")
    if _int_value(row.get("warning_count")) != 0 or _messages(row.get("warnings")):
        failures.append(f"{pair} has warnings")
    if _int_value(row.get("failure_count")) != 0 or _messages(row.get("failures")):
        failures.append(f"{pair} has failures")
    return failures


def _selected_hashes_and_failures(
    *,
    repo_root: Path,
    source_manifest: Mapping[str, Any],
    pairs: Iterable[tuple[str, int]],
) -> tuple[dict[str, str], list[str]]:
    hash_map = source_manifest.get("output_file_hashes")
    source_output_root = resolve_path(repo_root, str(source_manifest.get("output_root")))
    projected_output_root = resolve_path(
        repo_root,
        readiness_gate.LABEL_INPUT_ROOT_BY_EVIDENCE_ROOT.get(
            ledger_gate.CANDIDATE_CAUSAL_ROOT,
            ledger_gate.CANDIDATE_CAUSAL_ROOT,
        ),
    )
    selected: dict[str, str] = {}
    failures: list[str] = []
    for market, year in sorted({(str(market), int(year)) for market, year in pairs}):
        source_output_path = source_output_root / market / f"{year}.parquet"
        projected_output_path = projected_output_root / market / f"{year}.parquet"
        raw_path, expected_hash = _matching_hash(repo_root, hash_map, source_output_path)
        if raw_path is None or expected_hash is None:
            failures.append(f"output hash reference missing: {rel(source_output_path, repo_root)}")
            continue
        if expected_hash in {"", "MISSING", "NOT_WRITTEN"}:
            failures.append(f"output hash reference invalid: {rel(source_output_path, repo_root)}")
            continue
        if not projected_output_path.exists():
            failures.append(f"projected output missing: {rel(projected_output_path, repo_root)}")
            continue
        actual_hash = file_sha256(projected_output_path)
        if actual_hash != expected_hash:
            failures.append(f"projected output hash stale: {rel(projected_output_path, repo_root)}")
            continue
        selected[projected_output_path.as_posix()] = expected_hash
    return selected, failures


def _selected_input_hashes(source_manifest: Mapping[str, Any], selected_rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    input_hashes = source_manifest.get("input_file_hashes")
    if not isinstance(input_hashes, Mapping):
        return {}
    selected_paths = {str(row.get("input_path")) for row in selected_rows if row.get("input_path")}
    return {str(path): str(raw_hash) for path, raw_hash in input_hashes.items() if str(path) in selected_paths}


def _selected_summary(selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "file_count": len(selected_rows),
        "pass_count": len(selected_rows),
        "warn_count": 0,
        "fail_count": 0,
        "raw_rows": sum(_int_value(row.get("raw_rows")) for row in selected_rows),
        "output_rows": sum(_int_value(row.get("output_rows")) for row in selected_rows),
        "synthetic_rows": sum(_int_value(row.get("synthetic_rows")) for row in selected_rows),
        "synthetic_gap_count": sum(_int_value(row.get("synthetic_gap_count")) for row in selected_rows),
        "max_synthetic_gap_minutes": max(
            [_int_value(row.get("max_synthetic_gap_minutes")) for row in selected_rows] or [0]
        ),
        "degraded_bar_rows": sum(_int_value(row.get("degraded_bar_rows")) for row in selected_rows),
        "degraded_session_rows": sum(_int_value(row.get("degraded_session_rows")) for row in selected_rows),
        "roll_boundary_count": sum(_int_value(row.get("roll_boundary_count")) for row in selected_rows),
        "roll_window_count": sum(_int_value(row.get("roll_window_count")) for row in selected_rows),
        "local_trade_ohlcv_gap_gate_status": "NOT_RUN",
    }


def _target_profile(repo_root: Path, year: int, profile_config: Path) -> tuple[str | None, str | None]:
    profile = readiness_gate.YEAR_PROFILE_COMMANDS.get(year)
    if profile is None:
        return None, None
    scope = load_profile_scope(profile, profile_config, strict=False)
    return profile, scope.resolved_profile if scope is not None else None


def _projection_dir(reports_root: Path, profile: str, year: int) -> Path:
    return reports_root / f"{profile}_{year}"


def _projected_manifest(
    *,
    repo_root: Path,
    source_manifest: Mapping[str, Any],
    source_manifest_path: Path,
    source_manifest_sha256: str,
    selected_rows: list[dict[str, Any]],
    selected_hashes: dict[str, str],
    target_profile: str,
    target_resolved_profile: str | None,
    reports_root: Path | None,
    projected_output_root: Path,
    generated_at_utc: str,
) -> dict[str, Any]:
    projected_rows = copy.deepcopy(selected_rows)
    for row in projected_rows:
        row["output_path"] = (projected_output_root / str(row["market"]) / f"{int(row['year'])}.parquet").as_posix()
    pairs = [{"market": row["market"], "year": int(row["year"])} for row in projected_rows]
    year = int(selected_rows[0]["year"])
    markets = sorted(str(row["market"]) for row in projected_rows)
    projected = copy.deepcopy(dict(source_manifest))
    projected.update(
        {
            "generated_at": generated_at_utc,
            "stage": "causal_base",
            "status": "PASS",
            "profile": target_profile,
            "resolved_profile": target_resolved_profile,
            "output_root": projected_output_root.as_posix(),
            "reports_root": rel(_projection_dir(reports_root, target_profile, year), repo_root)
            if reports_root is not None
            else None,
            "markets": markets,
            "years": [year],
            "market_filter": markets,
            "year_filter": [year],
            "requested_market_years": pairs,
            "processed_market_years": pairs,
            "processed_market_year_count": len(pairs),
            "market_year_include_count": len(pairs),
            "selected_expected_market_year_count": len(pairs),
            "outputs": projected_rows,
            "input_file_hashes": _selected_input_hashes(source_manifest, selected_rows),
            "output_file_hashes": selected_hashes,
            "warning_count": 0,
            "failure_count": 0,
            "warnings": [],
            "failures": [],
            "summary": _selected_summary(selected_rows),
            "projection": {
                "stage": STAGE,
                "approved_scope": "candidate-root profile projection only",
                "source_manifest": rel(source_manifest_path, repo_root),
                "source_manifest_sha256": source_manifest_sha256,
                "source_profile": source_manifest.get("profile"),
                "source_resolved_profile": source_manifest.get("resolved_profile"),
                "target_profile": target_profile,
                "target_resolved_profile": target_resolved_profile,
                "market_years": pairs,
                "parquet_data_mutated": False,
                "repaired_root_warnings_accepted": False,
                "labels_or_features_approved": False,
            },
        }
    )
    return projected


def _ensure_reports_root(repo_root: Path, reports_root: Path) -> None:
    try:
        reports_root.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError as exc:
        raise ValueError(f"reports root must be under reports/: {rel(reports_root, repo_root)}") from exc


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    source_manifest_path: Path,
    reports_root: Path | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    approved_markets: Iterable[str] = DEFAULT_APPROVED_MARKETS,
    approved_years: Iterable[int] = DEFAULT_APPROVED_YEARS,
    profile_config: Path | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or utc_now()
    profile_config_path = profile_config or (repo_root / readiness_gate.DEFAULT_PROFILE_CONFIG)
    proposal = read_json(proposal_path)
    proposal_summary = proposal.get("summary") if isinstance(proposal.get("summary"), dict) else {}
    rows = _proposal_rows(proposal)
    candidate_rows = _candidate_rows(rows)
    repaired_rows = _repaired_rows(rows)
    candidate_pairs = sorted(pair for row in candidate_rows if (pair := _row_pair(row)) is not None)
    approved_pair_set = {
        (str(market), int(year))
        for market in approved_markets
        for year in approved_years
    }
    candidate_pair_set = set(candidate_pairs)
    staged_paths = sorted(staged_generated_paths) if staged_generated_paths is not None else _git_staged_generated_paths(repo_root)

    source_manifest = read_json(source_manifest_path)
    source_manifest_sha256 = ledger_gate.sha256_file(source_manifest_path) if source_manifest_path.exists() else ""
    source_output_root = resolve_path(repo_root, ledger_gate.CANDIDATE_CAUSAL_ROOT)
    projected_output_root = resolve_path(
        repo_root,
        readiness_gate.LABEL_INPUT_ROOT_BY_EVIDENCE_ROOT.get(
            ledger_gate.CANDIDATE_CAUSAL_ROOT,
            ledger_gate.CANDIDATE_CAUSAL_ROOT,
        ),
    )
    source_rows = _output_rows(source_manifest)
    selected_rows: dict[tuple[str, int], dict[str, Any]] = {}
    selected_row_failures: list[str] = []
    for pair in sorted(approved_pair_set):
        row = source_rows.get(pair)
        if row is None:
            selected_row_failures.append(f"source manifest output missing: {pair[0]}:{pair[1]}")
            continue
        failures = _clean_row_failures(row)
        if failures:
            selected_row_failures.extend(failures)
        selected_rows[pair] = copy.deepcopy(row)

    selected_hashes, hash_failures = _selected_hashes_and_failures(
        repo_root=repo_root,
        source_manifest=source_manifest,
        pairs=approved_pair_set,
    )

    target_failures: list[str] = []
    grouped: dict[int, list[dict[str, Any]]] = {}
    target_profiles: dict[int, tuple[str, str | None]] = {}
    for market, year in sorted(approved_pair_set):
        target_profile, target_resolved_profile = _target_profile(repo_root, year, profile_config_path)
        if target_profile is None:
            target_failures.append(f"no configured target profile for {year}")
            continue
        target_profiles[year] = (target_profile, target_resolved_profile)
        row = selected_rows.get((market, year))
        if row is not None:
            grouped.setdefault(year, []).append(row)

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proposal_review_ready",
        passed=proposal_summary.get("status") == proposal_gate.STATUS_READY,
        observed=proposal_summary.get("status"),
        expected=proposal_gate.STATUS_READY,
        detail="Candidate manifest projection requires the reviewed proof-status proposal.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged during profile projection.",
    )
    _check(
        checks,
        name="candidate_scope_matches_human_approval",
        passed=candidate_pair_set == approved_pair_set,
        observed=[f"{market}:{year}" for market, year in sorted(candidate_pair_set)],
        expected=[f"{market}:{year}" for market, year in sorted(approved_pair_set)],
        detail="This implementation is limited to the approved candidate-root HO/NG/RB 2025/2026 scope.",
    )
    _check(
        checks,
        name="source_manifest_is_pass_all_raw_candidate_root",
        passed=(
            source_manifest.get("stage") == "causal_base"
            and source_manifest.get("status") == "PASS"
            and source_manifest.get("profile") == ALL_RAW_PROFILE
            and source_manifest.get("resolved_profile") == ALL_RAW_PROFILE
            and _paths_equivalent(repo_root, source_manifest.get("output_root"), source_output_root)
            and _int_value(source_manifest.get("warning_count")) == 0
            and _int_value(source_manifest.get("failure_count")) == 0
        ),
        observed={
            "stage": source_manifest.get("stage"),
            "status": source_manifest.get("status"),
            "profile": source_manifest.get("profile"),
            "resolved_profile": source_manifest.get("resolved_profile"),
            "output_root": source_manifest.get("output_root"),
            "warning_count": source_manifest.get("warning_count"),
            "failure_count": source_manifest.get("failure_count"),
        },
        expected="PASS all_raw causal_base manifest rooted in the candidate causal root with no warnings or failures",
        detail="Projection may only re-label existing clean candidate manifest evidence; it must not repair data.",
    )
    _check(
        checks,
        name="selected_source_outputs_clean",
        passed=not selected_row_failures,
        observed=selected_row_failures,
        expected=[],
        detail="Every approved selected output row must remain PASS with no warnings or failures.",
    )
    _check(
        checks,
        name="selected_output_hashes_current",
        passed=not hash_failures and len(selected_hashes) == len(approved_pair_set),
        observed=hash_failures,
        expected=[],
        detail="Projected manifests must reference existing candidate parquet outputs with current hashes.",
    )
    _check(
        checks,
        name="target_profiles_resolved",
        passed=not target_failures and len(target_profiles) == len(set(approved_years)),
        observed=target_failures,
        expected="configured tier_3 holdout/forward target profiles for approved years",
        detail="Projection metadata must match the Phase 3 command profiles used by baseline readiness.",
    )
    _check(
        checks,
        name="repaired_root_rows_rejected_for_this_path",
        passed=True,
        observed=[_row_pair_label(row) for row in repaired_rows],
        expected="not projected; separate bounded causal-base repair diagnostic/repair approval required",
        detail="The approved direction rejects accepted-warning-only handling for repaired-root warning rows.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    projected_manifests: list[dict[str, Any]] = []
    if not failures:
        for year, rows_for_year in sorted(grouped.items()):
            target_profile, target_resolved_profile = target_profiles[year]
            output_dir = _projection_dir(reports_root, target_profile, year) if reports_root is not None else None
            manifest = _projected_manifest(
                repo_root=repo_root,
                source_manifest=source_manifest,
                source_manifest_path=source_manifest_path,
                source_manifest_sha256=source_manifest_sha256,
                selected_rows=sorted(rows_for_year, key=lambda row: str(row["market"])),
                selected_hashes={
                    path: raw_hash
                    for path, raw_hash in selected_hashes.items()
                    if Path(path).name == f"{year}.parquet"
                },
                target_profile=target_profile,
                target_resolved_profile=target_resolved_profile,
                reports_root=reports_root,
                projected_output_root=projected_output_root,
                generated_at_utc=generated_at,
            )
            projected_manifests.append(
                {
                    "year": year,
                    "markets": sorted(str(row["market"]) for row in rows_for_year),
                    "target_profile": target_profile,
                    "target_resolved_profile": target_resolved_profile,
                    "output_dir": rel(output_dir, repo_root) if output_dir is not None else None,
                    "manifest_path": rel(output_dir / "causal_base_manifest.json", repo_root)
                    if output_dir is not None
                    else None,
                    "markdown_path": rel(output_dir / "causal_base_manifest.md", repo_root)
                    if output_dir is not None
                    else None,
                    "manifest": manifest,
                }
            )

    status = STATUS_NO_GO if failures else STATUS_PROJECTED
    generated_output_count = 2 * len(projected_manifests) if reports_root is not None and not failures else 0
    approval_flags = {flag: False for flag in FALSE_APPROVAL_FLAGS}
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at,
            "status": status,
            "decision": DECISION_BLOCKED if failures else DECISION_APPROVED,
            "input_proposal": rel(proposal_path, repo_root),
            "input_source_manifest": rel(source_manifest_path, repo_root),
            "input_source_manifest_sha256": source_manifest_sha256,
            "candidate_projection_approved": not failures,
            "candidate_projection_market_year_count": len(candidate_pairs),
            "candidate_projection_manifest_count": len(projected_manifests),
            "repaired_root_market_year_count": len([row for row in repaired_rows if _row_pair(row) is not None]),
            "repaired_root_warnings_accepted": False,
            "reports_root": rel(reports_root, repo_root) if reports_root is not None else None,
            "generated_report_written": reports_root is not None and not failures,
            "generated_output_count": generated_output_count,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": (
                "Rerun baseline readiness; if only repaired-root warning groups remain blocked, approve a bounded "
                "causal-base repair diagnostic/repair path for those repaired-root market-years before labels/features."
            )
            if not failures
            else "Resolve failed projection checks, then rerun this projection gate.",
            **approval_flags,
        },
        "checks": checks,
        "projected_manifests": projected_manifests,
        "repaired_root_rows_rejected": [_row_pair_label(row) for row in repaired_rows],
        "staged_generated_paths": staged_paths,
        "non_approval": {
            "scope": "candidate-root manifest profile projection only",
            "repaired_root_warnings_accepted": False,
            **approval_flags,
        },
    }


def render_markdown(manifest: Mapping[str, Any]) -> str:
    projection = manifest.get("projection") if isinstance(manifest.get("projection"), Mapping) else {}
    rows = manifest.get("outputs") if isinstance(manifest.get("outputs"), list) else []
    lines = [
        "# Projected Local Trade Candidate Causal-Base Manifest",
        "",
        f"- Generated at UTC: {manifest.get('generated_at')}",
        "- Scope: candidate-root manifest profile projection only; parquet data is not mutated.",
        f"- Source manifest: `{projection.get('source_manifest')}`.",
        f"- Source profile: `{projection.get('source_profile')}` -> target profile `{manifest.get('profile')}`.",
        f"- Target resolved profile: `{manifest.get('resolved_profile')}`.",
        f"- Output root: `{manifest.get('output_root')}`.",
        f"- Market-years: {len(rows)}.",
        "- Repaired-root warnings accepted: `false`.",
        "- Labels/features/modeling/WFA/metrics/predictions approved: `false`.",
        "",
        "## Selected Outputs",
        "",
        "| market-year | status | warnings | failures |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in rows:
        if isinstance(row, Mapping):
            lines.append(
                f"| `{row.get('market')}:{row.get('year')}` | `{row.get('status')}` | "
                f"{_int_value(row.get('warning_count'))} | {_int_value(row.get('failure_count'))} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_projected_manifests(report: dict[str, Any], *, repo_root: Path, reports_root: Path) -> None:
    _ensure_reports_root(repo_root, reports_root)
    if report["summary"]["status"] != STATUS_PROJECTED:
        raise ValueError("cannot write projected manifests when projection checks failed")
    for item in report["projected_manifests"]:
        manifest_path = resolve_path(repo_root, str(item["manifest_path"]))
        markdown_path = resolve_path(repo_root, str(item["markdown_path"]))
        _ensure_reports_root(repo_root, manifest_path)
        _ensure_reports_root(repo_root, markdown_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(item["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(item["manifest"]), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    parser.add_argument("--source-manifest", default=str(DEFAULT_SOURCE_MANIFEST))
    parser.add_argument(
        "--reports-root",
        help=(
            "Optional generated reports root. When set, writes one causal_base_manifest.json and "
            "one causal_base_manifest.md per approved year under this reports/ path."
        ),
    )
    parser.add_argument("--approved-markets", default=",".join(DEFAULT_APPROVED_MARKETS))
    parser.add_argument("--approved-years", default=",".join(str(year) for year in DEFAULT_APPROVED_YEARS))
    parser.add_argument("--profile-config", default=str(readiness_gate.DEFAULT_PROFILE_CONFIG))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    source_manifest_path = resolve_path(repo_root, args.source_manifest)
    reports_root = resolve_path(repo_root, args.reports_root) if args.reports_root else None
    profile_config = resolve_path(repo_root, args.profile_config)
    try:
        report = build_report(
            repo_root=repo_root,
            proposal_path=proposal_path,
            source_manifest_path=source_manifest_path,
            reports_root=reports_root,
            approved_markets=_parse_csv(args.approved_markets),
            approved_years=_parse_years(args.approved_years),
            profile_config=profile_config,
        )
        if reports_root is not None:
            write_projected_manifests(report, repo_root=repo_root, reports_root=reports_root)
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1

    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"candidate_market_years={summary['candidate_projection_market_year_count']} "
        f"projected_manifests={summary['candidate_projection_manifest_count']} "
        f"repaired_root_rows_rejected={summary['repaired_root_market_year_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 0 if summary["status"] == STATUS_PROJECTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
