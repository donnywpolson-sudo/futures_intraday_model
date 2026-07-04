#!/usr/bin/env python3
"""Build a read-only ledger of accepted local-trade evidence reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as proof_gate


STAGE = "local_trade_accepted_evidence_ledger"
STATUS_READY = "REVIEW_READY_ACCEPTED_EVIDENCE_LEDGER"
STATUS_NO_GO = "NO_GO_ACCEPTED_EVIDENCE_LEDGER"
DECISION_REVIEW_ONLY = "review_only_no_promotion"

DEFAULT_TIER1_REPORT = proof_gate.DEFAULT_LOCAL_TRADE_REPORT
DEFAULT_SHARDS_ROOT = (
    REPO_ROOT / "reports/pipeline_audit/local_trade_shards_20250618_20260613"
)
DEFAULT_JSON_OUT = (
    REPO_ROOT
    / "reports/pipeline_audit/local_trade_accepted_evidence_ledger_20250618_20260613.json"
)
DEFAULT_MARKDOWN_OUT = DEFAULT_JSON_OUT.with_suffix(".md")

EXPECTED_ACCESS_WINDOW = proof_gate.EXPECTED_ACCESS_WINDOW
EXPECTED_DBN_ROOT = proof_gate.EXPECTED_DBN_ROOT
EXPECTED_RAW_ROOT = proof_gate.EXPECTED_RAW_ROOT
TIER1_CAUSAL_ROOT = "data/causally_gated_normalized"
CANDIDATE_CAUSAL_ROOT = "data/causal_proof_candidates/local_trade_2025_2026_v1"
CAVEAT_TERMS = proof_gate.CAVEAT_TERMS
FAILED_CLASSIFICATIONS = proof_gate.FAILED_CLASSIFICATIONS

EXPECTED_SHARD_SETS: tuple[dict[str, Any], ...] = (
    {
        "name": "NG_2025_split_v1",
        "market": "NG",
        "year": 2025,
        "relative_dir": "NG_2025_split_v1",
        "pattern": "NG_2025_w*.json",
        "expected_count": 28,
    },
    {
        "name": "remaining_v1/NG_2026",
        "market": "NG",
        "year": 2026,
        "relative_file": "remaining_v1/NG_2026.json",
        "expected_count": 1,
    },
    {
        "name": "RB_2025_split_v1",
        "market": "RB",
        "year": 2025,
        "relative_dir": "RB_2025_split_v1",
        "pattern": "RB_2025_w*.json",
        "expected_count": 28,
    },
    {
        "name": "RB_2026_split_v1",
        "market": "RB",
        "year": 2026,
        "relative_dir": "RB_2026_split_v1",
        "pattern": "RB_2026_w*.json",
        "expected_count": 24,
    },
    {
        "name": "HO_2025_split_v1",
        "market": "HO",
        "year": 2025,
        "relative_dir": "HO_2025_split_v1",
        "pattern": "HO_2025_w*.json",
        "expected_count": 28,
    },
    {
        "name": "HO_2026_split_v1",
        "market": "HO",
        "year": 2026,
        "relative_dir": "HO_2026_split_v1",
        "pattern": "HO_2026_w*.json",
        "expected_count": 24,
    },
)

SUPERSEDED_REPORTS: tuple[str, ...] = (
    "remaining_v1/RB_2025.json",
    "HO_2025.json",
    "remaining_v1/HO_2026.json",
)

FALSE_APPROVAL_FLAGS: tuple[str, ...] = (
    "data_mutation_performed",
    "canonical_promotion_approved",
    "proof_status_promoted",
    "generated_artifacts_staged",
    "modeling_approved",
    "wfa_approved",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _year_window(year: int) -> dict[str, str]:
    if year == 2025:
        return {
            "start": EXPECTED_ACCESS_WINDOW["start"],
            "end": "2026-01-01T00:00:00Z",
        }
    if year == 2026:
        return {
            "start": "2026-01-01T00:00:00Z",
            "end": EXPECTED_ACCESS_WINDOW["end"],
        }
    return dict(EXPECTED_ACCESS_WINDOW)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _window_matches(value: Any, expected: dict[str, str] = EXPECTED_ACCESS_WINDOW) -> bool:
    return isinstance(value, dict) and value.get("start") == expected["start"] and value.get("end") == expected["end"]


def _window_inside_access(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start = _parse_utc(value.get("start"))
    end = _parse_utc(value.get("end"))
    access_start = _parse_utc(EXPECTED_ACCESS_WINDOW["start"])
    access_end = _parse_utc(EXPECTED_ACCESS_WINDOW["end"])
    return bool(start and end and access_start and access_end and access_start <= start < end <= access_end)


def _has_required_caveat(report: dict[str, Any]) -> bool:
    caveat = str(report.get("caveat", "")).lower()
    return all(term in caveat for term in CAVEAT_TERMS)


def _report_market_years(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("market_years")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _summary_counts(report: dict[str, Any]) -> dict[str, int]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "synthetic_gap_count": _as_int(summary.get("synthetic_gap_count")),
        "missing_minute_count": _as_int(summary.get("missing_minute_count")),
        "verified_empty_minutes": _as_int(summary.get("verified_empty_minutes")),
        "timestamp_basis_mismatch_minutes": _as_int(summary.get("timestamp_basis_mismatch_minutes")),
        "failed_minutes": _as_int(summary.get("failed_minutes")),
        "unverified_minutes": _as_int(summary.get("unverified_minutes")),
    }


def _add_counts(target: dict[str, int], counts: dict[str, int]) -> None:
    for key, value in counts.items():
        target[key] = target.get(key, 0) + int(value)


def _bad_entry_summaries(report: dict[str, Any]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for row in _report_market_years(report):
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        classifications = row.get("classification_counts") if isinstance(row.get("classification_counts"), dict) else {}
        failed_classifications = sorted(
            key
            for key, count in classifications.items()
            if _as_int(count) > 0 and str(key) in FAILED_CLASSIFICATIONS
        )
        if (
            row.get("status") != "PASS"
            or _as_int(summary.get("failed_minutes")) > 0
            or _as_int(summary.get("unverified_minutes")) > 0
            or failed_classifications
        ):
            bad.append(
                {
                    "market": row.get("market"),
                    "year": row.get("year"),
                    "status": row.get("status"),
                    "failed_minutes": summary.get("failed_minutes"),
                    "unverified_minutes": summary.get("unverified_minutes"),
                    "failed_classifications": failed_classifications,
                }
            )
    return bad


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


def _expected_shard_paths(shards_root: Path, spec: dict[str, Any]) -> list[Path]:
    if "relative_file" in spec:
        return [shards_root / str(spec["relative_file"])]
    base = shards_root / str(spec["relative_dir"])
    return sorted(base.glob(str(spec["pattern"])))


def _canonical_markets(phase2_manifest_path: Path) -> list[str]:
    if not phase2_manifest_path.exists():
        return []
    manifest = read_json(phase2_manifest_path)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        return []
    return sorted(
        {
            str(row["market"])
            for row in outputs
            if isinstance(row, dict) and isinstance(row.get("market"), str)
        }
    )


def _load_report(path: Path, *, repo_root: Path, role: str, group: str) -> dict[str, Any]:
    report = read_json(path)
    counts = _summary_counts(report)
    return {
        "path": rel(path, repo_root),
        "sha256": sha256_file(path),
        "role": role,
        "group": group,
        "status": report.get("status"),
        "failures": report.get("failures") if isinstance(report.get("failures"), list) else [],
        "dbn_root": report.get("dbn_root"),
        "raw_root": report.get("raw_root"),
        "causal_root": report.get("causal_root"),
        "window": report.get("window"),
        "local_trades_schema_access": report.get("local_trades_schema_access"),
        "counts": counts,
        "market_years": [
            {
                "market": row.get("market"),
                "year": row.get("year"),
                "status": row.get("status"),
                "summary": row.get("summary") if isinstance(row.get("summary"), dict) else {},
            }
            for row in _report_market_years(report)
        ],
        "_payload": report,
        "_path": path,
    }


def _tier1_acceptance_failure(row: dict[str, Any]) -> list[str]:
    report = row["_payload"]
    failures: list[str] = []
    if report.get("status") != "PASS":
        failures.append("status_not_pass")
    if report.get("failures"):
        failures.append("report_failures_present")
    if not _window_matches(report.get("window")):
        failures.append("window_not_full_access")
    if not _window_matches(report.get("local_trades_schema_access")):
        failures.append("schema_access_not_full_access")
    if report.get("dbn_root") != EXPECTED_DBN_ROOT or report.get("raw_root") != EXPECTED_RAW_ROOT:
        failures.append("dbn_or_raw_root_unexpected")
    if report.get("causal_root") != TIER1_CAUSAL_ROOT:
        failures.append("causal_root_not_repaired_tier1")
    if not _has_required_caveat(report):
        failures.append("non_direct_caveat_missing")
    counts = _summary_counts(report)
    if counts["failed_minutes"] or counts["unverified_minutes"]:
        failures.append("failed_or_unverified_minutes_present")
    if _bad_entry_summaries(report):
        failures.append("bad_market_year_entries")
    return failures


def _shard_acceptance_failure(row: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    report = row["_payload"]
    failures: list[str] = []
    if report.get("status") != "PASS":
        failures.append("status_not_pass")
    if report.get("failures"):
        failures.append("report_failures_present")
    if not _window_matches(report.get("local_trades_schema_access")):
        failures.append("schema_access_not_full_access")
    if not _window_inside_access(report.get("window")):
        failures.append("window_outside_access")
    if report.get("dbn_root") != EXPECTED_DBN_ROOT or report.get("raw_root") != EXPECTED_RAW_ROOT:
        failures.append("dbn_or_raw_root_unexpected")
    if report.get("causal_root") != CANDIDATE_CAUSAL_ROOT:
        failures.append("causal_root_not_candidate")
    if not _has_required_caveat(report):
        failures.append("non_direct_caveat_missing")
    counts = _summary_counts(report)
    if counts["failed_minutes"] or counts["unverified_minutes"]:
        failures.append("failed_or_unverified_minutes_present")
    bad_entries = _bad_entry_summaries(report)
    if bad_entries:
        failures.append("bad_market_year_entries")
    market_years = _report_market_years(report)
    if not market_years:
        failures.append("market_year_entries_missing")
    for market_year in market_years:
        if market_year.get("market") != spec["market"] or _as_int(market_year.get("year")) != spec["year"]:
            failures.append("market_year_does_not_match_expected_shard_set")
            break
    return failures


def _coverage_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        report = row["_payload"]
        window = report.get("window") if isinstance(report.get("window"), dict) else {}
        for market_year in _report_market_years(report):
            market = market_year.get("market")
            year = _as_int(market_year.get("year"))
            if isinstance(market, str) and year:
                by_pair.setdefault((market, year), []).append(
                    {
                        "path": row["path"],
                        "start": window.get("start"),
                        "end": window.get("end"),
                    }
                )

    failures: list[dict[str, Any]] = []
    for (market, year), windows in sorted(by_pair.items()):
        expected = _year_window(year)
        sortable = []
        for window in windows:
            start = _parse_utc(window.get("start"))
            end = _parse_utc(window.get("end"))
            if start is None or end is None:
                failures.append(
                    {
                        "market": market,
                        "year": year,
                        "reason": "unparseable_window",
                        "windows": windows,
                    }
                )
                continue
            sortable.append((start, end, window))
        if len(sortable) != len(windows):
            continue
        sortable.sort(key=lambda item: item[0])
        expected_start = _parse_utc(expected["start"])
        expected_end = _parse_utc(expected["end"])
        reasons: list[str] = []
        if not sortable or sortable[0][0] != expected_start:
            reasons.append("coverage_start_mismatch")
        if sortable and sortable[-1][1] != expected_end:
            reasons.append("coverage_end_mismatch")
        for previous, current in zip(sortable, sortable[1:]):
            if previous[1] != current[0]:
                reasons.append("gap_or_overlap_between_windows")
                break
        if reasons:
            failures.append(
                {
                    "market": market,
                    "year": year,
                    "reason": ",".join(reasons),
                    "expected": expected,
                    "observed": [
                        {
                            "path": item[2]["path"],
                            "start": _format_utc(item[0]),
                            "end": _format_utc(item[1]),
                        }
                        for item in sortable
                    ],
                }
            )
    return failures


def _market_year_coverage(rows: Iterable[dict[str, Any]], *, root_classification: str) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for row in rows:
        report = row["_payload"]
        window = report.get("window") if isinstance(report.get("window"), dict) else {}
        for market_year in _report_market_years(report):
            coverage.append(
                {
                    "market": market_year.get("market"),
                    "year": market_year.get("year"),
                    "report_path": row["path"],
                    "report_role": row["role"],
                    "root_classification": root_classification,
                    "causal_root": row["causal_root"],
                    "window": window,
                    "status": market_year.get("status"),
                }
            )
    return coverage


def _scrub_input_report(row: dict[str, Any], *, root_classification: str | None = None) -> dict[str, Any]:
    clean = {
        key: value
        for key, value in row.items()
        if key not in {"_payload", "_path"}
    }
    if root_classification:
        clean["root_classification"] = root_classification
    return clean


def build_report(
    *,
    repo_root: Path,
    tier1_report_path: Path,
    accepted_shards_root: Path,
    phase2_manifest_path: Path,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    unreadable_reports: list[dict[str, str]] = []

    tier1_row: dict[str, Any] | None = None
    if tier1_report_path.exists():
        try:
            tier1_row = _load_report(
                tier1_report_path,
                repo_root=repo_root,
                role="tier1_repaired",
                group="tier1_repaired_access_window",
            )
        except Exception as exc:
            unreadable_reports.append(
                {"path": rel(tier1_report_path, repo_root), "error": f"{type(exc).__name__}: {exc}"}
            )

    shard_rows: list[dict[str, Any]] = []
    missing_shard_paths: list[str] = []
    shard_set_summaries: list[dict[str, Any]] = []
    for spec in EXPECTED_SHARD_SETS:
        paths = _expected_shard_paths(accepted_shards_root, spec)
        actual_count = len(paths)
        if actual_count != spec["expected_count"]:
            expected_path = str(spec.get("relative_file") or f"{spec['relative_dir']}/{spec['pattern']}")
            missing_shard_paths.append(f"{spec['name']} expected {spec['expected_count']} at {expected_path}; found {actual_count}")
        loaded_count = 0
        for path in paths:
            if not path.exists():
                missing_shard_paths.append(rel(path, repo_root))
                continue
            try:
                shard_rows.append(
                    _load_report(
                        path,
                        repo_root=repo_root,
                        role="candidate_recovery_shard",
                        group=str(spec["name"]),
                    )
                )
                loaded_count += 1
            except Exception as exc:
                unreadable_reports.append(
                    {"path": rel(path, repo_root), "error": f"{type(exc).__name__}: {exc}"}
                )
        shard_set_summaries.append(
            {
                "name": spec["name"],
                "market": spec["market"],
                "year": spec["year"],
                "expected_count": spec["expected_count"],
                "found_count": actual_count,
                "loaded_count": loaded_count,
            }
        )

    superseded_rows: list[dict[str, Any]] = []
    for relative_path in SUPERSEDED_REPORTS:
        path = accepted_shards_root / relative_path
        if path.exists():
            try:
                superseded_rows.append(
                    _load_report(
                        path,
                        repo_root=repo_root,
                        role="superseded_excluded",
                        group="superseded_monolithic_failures",
                    )
                )
            except Exception as exc:
                unreadable_reports.append(
                    {"path": rel(path, repo_root), "error": f"{type(exc).__name__}: {exc}"}
                )

    selected_paths = {row["path"] for row in [*([] if tier1_row is None else [tier1_row]), *shard_rows, *superseded_rows]}
    all_shard_json = sorted(accepted_shards_root.rglob("*.json")) if accepted_shards_root.exists() else []
    unselected_reports = [
        rel(path, repo_root)
        for path in all_shard_json
        if rel(path, repo_root) not in selected_paths
    ]

    tier1_failures = _tier1_acceptance_failure(tier1_row) if tier1_row is not None else ["tier1_report_missing"]
    shard_failures: list[dict[str, Any]] = []
    for row in shard_rows:
        spec = next(spec for spec in EXPECTED_SHARD_SETS if spec["name"] == row["group"])
        failures = _shard_acceptance_failure(row, spec)
        if failures:
            shard_failures.append({"path": row["path"], "failures": failures})
    coverage_failures = _coverage_failures(shard_rows)

    expected_shard_count = sum(int(spec["expected_count"]) for spec in EXPECTED_SHARD_SETS)
    _check(
        checks,
        name="tier1_repaired_report_accepted",
        passed=tier1_row is not None and not tier1_failures,
        observed=tier1_failures,
        expected=[],
        detail="The repaired Tier 1 report must be PASS, clean, full-window, and rooted in the accepted repaired Tier 1 causal root.",
    )
    _check(
        checks,
        name="accepted_shard_file_count",
        passed=not missing_shard_paths and len(shard_rows) == expected_shard_count,
        observed={"loaded": len(shard_rows), "missing_or_count_mismatches": missing_shard_paths},
        expected={"loaded": expected_shard_count, "missing_or_count_mismatches": []},
        detail="The ledger must read exactly the 133 accepted generated PASS shard reports.",
    )
    _check(
        checks,
        name="accepted_shard_reports_clean",
        passed=not shard_failures,
        observed=shard_failures,
        expected=[],
        detail="Accepted generated shard reports must be PASS, clean, full schema-access, candidate-root evidence.",
    )
    _check(
        checks,
        name="accepted_shard_windows_contiguous",
        passed=not coverage_failures,
        observed=coverage_failures,
        expected="per market-year candidate windows cover the expected 2025/2026 access subwindow without gaps or overlaps",
        detail="Split candidate shards must reconcile to complete market-year access-window coverage.",
    )
    _check(
        checks,
        name="superseded_monolithic_failures_excluded",
        passed=not any(row["path"] in {item["path"] for item in shard_rows} for row in superseded_rows),
        observed=[{"path": row["path"], "status": row["status"], "failures": row["failures"]} for row in superseded_rows],
        expected="listed only as superseded_excluded, never accepted evidence",
        detail="Superseded monolithic FAIL reports must be recorded as excluded and must not affect accepted evidence status.",
    )
    _check(
        checks,
        name="candidate_root_classified_not_promoted",
        passed=all(row["causal_root"] == CANDIDATE_CAUSAL_ROOT for row in shard_rows),
        observed=sorted({str(row["causal_root"]) for row in shard_rows}),
        expected=CANDIDATE_CAUSAL_ROOT,
        detail="Candidate-root shard evidence must remain classified as candidate-derived review evidence.",
    )
    _check(
        checks,
        name="input_reports_readable",
        passed=not unreadable_reports,
        observed=unreadable_reports,
        expected=[],
        detail="Selected input reports must be valid JSON objects.",
    )

    accepted_rows = [*([] if tier1_row is None or tier1_failures else [tier1_row]), *([] if shard_failures else shard_rows)]
    tier1_counts: dict[str, int] = {}
    candidate_counts: dict[str, int] = {}
    aggregate_counts: dict[str, int] = {}
    if tier1_row is not None and not tier1_failures:
        _add_counts(tier1_counts, tier1_row["counts"])
        _add_counts(aggregate_counts, tier1_row["counts"])
    if not shard_failures:
        for row in shard_rows:
            _add_counts(candidate_counts, row["counts"])
            _add_counts(aggregate_counts, row["counts"])

    tier1_coverage = _market_year_coverage(
        [tier1_row] if tier1_row is not None and not tier1_failures else [],
        root_classification="repaired_tier1_convention_evidence",
    )
    candidate_coverage = _market_year_coverage(
        shard_rows if not shard_failures else [],
        root_classification="candidate_derived_review_evidence",
    )
    coverage_rows = tier1_coverage + candidate_coverage
    accepted_pairs = sorted(
        {
            f"{row['market']}:{row['year']}"
            for row in coverage_rows
            if row.get("market") is not None and row.get("year") is not None
        }
    )
    accepted_markets = sorted(
        {
            str(row["market"])
            for row in coverage_rows
            if isinstance(row.get("market"), str)
        }
    )
    canonical_markets = _canonical_markets(phase2_manifest_path)
    uncovered_canonical_markets = sorted(set(canonical_markets) - set(accepted_markets))

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_READY if not failures else STATUS_NO_GO
    summary = {
        "stage": STAGE,
        "generated_at_utc": generated_at_utc or utc_now(),
        "status": status,
        "decision": DECISION_REVIEW_ONLY,
        "input_report_count": len([row for row in [tier1_row] if row is not None]) + len(shard_rows),
        "accepted_report_count": len(accepted_rows),
        "tier1_report_count": 1 if tier1_row is not None and not tier1_failures else 0,
        "accepted_shard_report_count": len(shard_rows) if not shard_failures else 0,
        "expected_accepted_shard_report_count": expected_shard_count,
        "excluded_report_count": len(superseded_rows),
        "unselected_report_count": len(unselected_reports),
        "accepted_market_year_count": len(accepted_pairs),
        "accepted_market_count": len(accepted_markets),
        "canonical_market_count": len(canonical_markets),
        "uncovered_canonical_market_count": len(uncovered_canonical_markets),
        "aggregate_counts": aggregate_counts,
        "tier1_counts": tier1_counts,
        "candidate_recovery_counts": candidate_counts,
        "candidate_root": CANDIDATE_CAUSAL_ROOT,
        "candidate_root_promoted_to_canonical": False,
        "review_only_no_promotion": True,
        "reports_generated_only": True,
        "data_mutation_performed": False,
        "canonical_promotion_approved": False,
        "proof_status_promoted": False,
        "generated_artifacts_staged": False,
        "modeling_approved": False,
        "wfa_approved": False,
        "live_or_paper_execution_approved": False,
        "failure_count": len(failures),
    }
    return {
        "summary": summary,
        "checks": checks,
        "shard_sets": shard_set_summaries,
        "input_reports": [
            *(
                []
                if tier1_row is None
                else [_scrub_input_report(tier1_row, root_classification="repaired_tier1_convention_evidence")]
            ),
            *[
                _scrub_input_report(row, root_classification="candidate_derived_review_evidence")
                for row in shard_rows
            ],
        ],
        "excluded_reports": [
            _scrub_input_report(row, root_classification="superseded_excluded_not_accepted")
            for row in superseded_rows
        ],
        "unselected_reports": unselected_reports,
        "coverage": {
            "accepted_market_years": accepted_pairs,
            "accepted_markets": accepted_markets,
            "canonical_markets": canonical_markets,
            "uncovered_canonical_markets": uncovered_canonical_markets,
            "rows": coverage_rows,
        },
        "non_approval": {
            "scope": "generated review ledger only",
            "canonical_promotion_approved": False,
            "proof_status_promoted": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = report["coverage"]
    lines = [
        "# Local Trade Accepted Evidence Ledger",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: read-only generated review ledger for accepted local-trade evidence.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Accepted reports: {summary['accepted_report_count']} total; "
        f"{summary['accepted_shard_report_count']}/{summary['expected_accepted_shard_report_count']} generated shard reports.",
        f"- Accepted markets: {summary['accepted_market_count']}; uncovered canonical markets: {summary['uncovered_canonical_market_count']}.",
        f"- Aggregate counts: `{json.dumps(summary['aggregate_counts'], sort_keys=True)}`.",
        "",
        "## Non-Approval Flags",
        "",
        "- This ledger is review-only and does not approve canonical promotion, proof-status promotion, generated-artifact staging, modeling, WFA, metrics, predictions, or live/paper execution.",
        "- `reports_generated_only`: true.",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")

    lines.extend(["", "## Accepted Shard Sets", "", "| set | market | year | loaded | expected |", "| --- | --- | --- | --- | --- |"])
    for row in report["shard_sets"]:
        lines.append(
            f"| `{row['name']}` | `{row['market']}` | {row['year']} | {row['loaded_count']} | {row['expected_count']} |"
        )

    lines.extend(["", "## Accepted Evidence Coverage", "", "| market-year | source classification |", "| --- | --- |"])
    classifications_by_pair: dict[str, set[str]] = {}
    for row in coverage["rows"]:
        pair = f"{row['market']}:{row['year']}"
        classifications_by_pair.setdefault(pair, set()).add(str(row["root_classification"]))
    for pair in sorted(classifications_by_pair):
        lines.append(f"| `{pair}` | `{', '.join(sorted(classifications_by_pair[pair]))}` |")

    lines.extend(["", "## Superseded Excluded Reports", "", "| path | status | failures |", "| --- | --- | --- |"])
    for row in report["excluded_reports"]:
        failures = "; ".join(str(item) for item in row.get("failures", []))
        lines.append(f"| `{row['path']}` | `{row['status']}` | {failures} |")

    lines.extend(["", "## Uncovered Canonical Markets", ""])
    if coverage["uncovered_canonical_markets"]:
        lines.append(f"- `{', '.join(coverage['uncovered_canonical_markets'])}`")
    else:
        lines.append("- None.")

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
    parser.add_argument("--tier1-report", default=str(DEFAULT_TIER1_REPORT))
    parser.add_argument("--accepted-shards-root", default=str(DEFAULT_SHARDS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(scope_gate.DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    tier1_report_path = resolve_path(repo_root, args.tier1_report)
    accepted_shards_root = resolve_path(repo_root, args.accepted_shards_root)
    phase2_manifest_path = resolve_path(repo_root, args.phase2_manifest)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(
            repo_root=repo_root,
            tier1_report_path=tier1_report_path,
            accepted_shards_root=accepted_shards_root,
            phase2_manifest_path=phase2_manifest_path,
        )
        write_report(report, repo_root=repo_root, json_out=json_out, markdown_out=markdown_out)
    except ValueError as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"accepted_reports={summary['accepted_report_count']} "
        f"accepted_shards={summary['accepted_shard_report_count']}/{summary['expected_accepted_shard_report_count']} "
        f"uncovered_canonical_markets={summary['uncovered_canonical_market_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0 if summary["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
