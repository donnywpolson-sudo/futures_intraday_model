#!/usr/bin/env python3
"""Report-only Phase 5 split-plan acceptance review."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.pipeline_gates import file_sha256
from scripts.validation.data_audit_universe_guard import load_data_audit_universe


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "phase5_split_plan_acceptance_review"
PASS_STATUS = "PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY"
FAIL_STATUS = "FAIL_PHASE5_SPLIT_PLAN_ACCEPTANCE_REVIEW"
DEFAULT_SPLIT_PLAN = Path("reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan.json")
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")
EXPECTED_PROFILE = "tier_1_core"
EXPECTED_RESOLVED_PROFILE = "tier_1_research"
EXPECTED_INPUT_ROOT = "data/feature_matrices"
EXPECTED_MARKETS = ["ES", "CL", "ZN", "6E"]
EXPECTED_YEARS = [2023, 2024]
EXPECTED_PURGE_BARS = 31
EXPECTED_EMBARGO_BARS = 31

NO_MUTATION_TEXT = (
    "Report-only split-plan acceptance review. No WFA/model training, prediction generation, "
    "provider calls, data replacement, cleanup/archive, staging, commit, push, paper, or live work "
    "is approved or performed."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must contain a JSON object")
    return payload


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def add_check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    evidence: Mapping[str, Any],
    failure: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "evidence": dict(evidence),
            "failure": None if passed else failure,
        }
    )
    if not passed:
        failures.append(f"{name}: {failure}")


def count_prediction_files(predictions_root: Path) -> int:
    if not predictions_root.exists():
        return 0
    return sum(1 for path in predictions_root.rglob("*") if path.is_file())


def expected_pairs(markets: list[str], years: list[int]) -> set[tuple[str, int]]:
    return {(market, year) for market in markets for year in years}


def fold_id(row: Mapping[str, Any]) -> str:
    return str(row.get("fold_id") or f"{row.get('market')}#{row.get('fold_number')}")


def check_folds(
    *,
    folds: list[Mapping[str, Any]],
    expected_purge_bars: int,
    expected_embargo_bars: int,
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    market_counter: Counter[str] = Counter()
    min_train_rows: int | None = None
    min_test_rows: int | None = None
    seen_fold_ids: set[str] = set()
    folds_by_market: dict[str, list[Mapping[str, Any]]] = {}

    required = {
        "market",
        "fold_id",
        "fold_number",
        "split_group",
        "selection_allowed",
        "train_start",
        "train_end",
        "purged_train_end",
        "test_start",
        "test_end",
        "embargo_end",
        "train_rows_before_purge",
        "train_rows_after_purge",
        "purged_train_rows",
        "test_rows",
        "embargo_rows",
        "purge_bars",
        "resolved_purge_bars",
        "embargo_bars",
    }
    for fold in folds:
        fid = fold_id(fold)
        missing = sorted(required - set(fold))
        if missing:
            failures.append(f"{fid}: missing required fields {missing}")
            continue
        if fid in seen_fold_ids:
            failures.append(f"{fid}: duplicate fold_id")
        seen_fold_ids.add(fid)

        market = str(fold.get("market") or "")
        market_counter[market] += 1
        folds_by_market.setdefault(market, []).append(fold)
        split_group = str(fold.get("split_group") or "")
        selection_allowed = bool_value(fold.get("selection_allowed"))
        if split_group != "research":
            failures.append(f"{fid}: split_group is {split_group!r}, not 'research'")
        if selection_allowed is not True:
            failures.append(f"{fid}: selection_allowed is not true")
        if bool(fold.get("is_final_holdout", fold.get("final_holdout", False))):
            failures.append(f"{fid}: final holdout flag is true for research split")

        train_start = parse_timestamp(fold.get("train_start"))
        train_end = parse_timestamp(fold.get("train_end"))
        purged_train_end = parse_timestamp(fold.get("purged_train_end"))
        test_start = parse_timestamp(fold.get("test_start"))
        test_end = parse_timestamp(fold.get("test_end"))
        embargo_end = parse_timestamp(fold.get("embargo_end"))
        if None in {train_start, train_end, purged_train_end, test_start, test_end, embargo_end}:
            failures.append(f"{fid}: one or more timestamps are invalid")
            continue
        assert train_start is not None
        assert train_end is not None
        assert purged_train_end is not None
        assert test_start is not None
        assert test_end is not None
        assert embargo_end is not None
        if train_start > purged_train_end:
            failures.append(f"{fid}: train_start after purged_train_end")
        if purged_train_end > train_end:
            failures.append(f"{fid}: purged_train_end after train_end")
        if train_end >= test_start:
            failures.append(f"{fid}: train_end overlaps test_start")
        if purged_train_end >= test_start:
            failures.append(f"{fid}: purged_train_end overlaps test_start")
        if test_start > test_end:
            failures.append(f"{fid}: test_start after test_end")
        if embargo_end < test_end:
            failures.append(f"{fid}: embargo_end before test_end")

        train_before = int_value(fold.get("train_rows_before_purge"))
        train_after = int_value(fold.get("train_rows_after_purge"))
        purged_rows = int_value(fold.get("purged_train_rows"))
        test_rows = int_value(fold.get("test_rows"))
        embargo_rows = int_value(fold.get("embargo_rows"))
        purge_bars = int_value(fold.get("purge_bars"))
        resolved_purge_bars = int_value(fold.get("resolved_purge_bars"))
        embargo_bars = int_value(fold.get("embargo_bars"))
        if train_before is None or train_after is None or purged_rows is None or test_rows is None:
            failures.append(f"{fid}: one or more row-count fields are invalid")
            continue
        if train_after <= 0:
            failures.append(f"{fid}: train_rows_after_purge is not positive")
        if test_rows <= 0:
            failures.append(f"{fid}: test_rows is not positive")
        if train_before < train_after:
            failures.append(f"{fid}: train_rows_before_purge < train_rows_after_purge")
        if train_before - train_after != purged_rows:
            failures.append(f"{fid}: purged_train_rows does not equal before-after")
        if purge_bars != expected_purge_bars or resolved_purge_bars != expected_purge_bars:
            failures.append(f"{fid}: purge bars do not match expected {expected_purge_bars}")
        if embargo_bars != expected_embargo_bars or embargo_rows != expected_embargo_bars:
            failures.append(f"{fid}: embargo bars/rows do not match expected {expected_embargo_bars}")
        min_train_rows = train_after if min_train_rows is None else min(min_train_rows, train_after)
        min_test_rows = test_rows if min_test_rows is None else min(min_test_rows, test_rows)

    for market, rows in folds_by_market.items():
        ordered = sorted(rows, key=lambda row: int_value(row.get("fold_number")) or -1)
        fold_numbers = [int_value(row.get("fold_number")) for row in ordered]
        expected_numbers = list(range(1, len(ordered) + 1))
        if fold_numbers != expected_numbers:
            failures.append(f"{market}: fold_number sequence is {fold_numbers}, not {expected_numbers}")
        previous_test_end: datetime | None = None
        previous_test_start: datetime | None = None
        for row in ordered:
            fid = fold_id(row)
            test_start = parse_timestamp(row.get("test_start"))
            test_end = parse_timestamp(row.get("test_end"))
            if test_start is None or test_end is None:
                continue
            if previous_test_start is not None and test_start <= previous_test_start:
                failures.append(f"{fid}: test_start is not strictly increasing")
            if previous_test_end is not None and test_start <= previous_test_end:
                failures.append(f"{fid}: test window overlaps previous fold")
            previous_test_start = test_start
            previous_test_end = test_end

    return failures, {
        "fold_count": len(folds),
        "fold_count_by_market": dict(sorted(market_counter.items())),
        "min_train_rows_after_purge": min_train_rows,
        "min_test_rows": min_test_rows,
        "duplicate_fold_id_count": len(folds) - len(seen_fold_ids),
    }


def csv_fold_ids(rows: list[Mapping[str, str]]) -> set[str]:
    return {str(row.get("fold_id") or "") for row in rows}


def validate_generated_scope(
    *,
    report_root: Path,
    allowed_paths: set[Path],
    repo_root: Path,
) -> tuple[list[str], dict[str, Any]]:
    if not report_root.exists():
        return [f"report root missing: {rel(report_root, repo_root)}"], {"existing_files": []}
    existing = {path for path in report_root.rglob("*") if path.is_file()}
    unexpected = sorted(rel(path, repo_root) for path in existing - allowed_paths)
    return (
        [f"unexpected files under split-plan report root: {unexpected}"] if unexpected else [],
        {
            "report_root": rel(report_root, repo_root),
            "existing_files": sorted(rel(path, repo_root) for path in existing),
            "allowed_files": sorted(rel(path, repo_root) for path in allowed_paths),
            "unexpected_files": unexpected,
        },
    )


def build_report(
    *,
    repo_root: Path,
    split_plan_path: Path,
    csv_path: Path,
    json_out: Path,
    md_out: Path,
    expected_profile: str,
    expected_resolved_profile: str,
    expected_input_root: str,
    expected_markets: list[str],
    expected_years: list[int],
    expected_purge_bars: int,
    expected_embargo_bars: int,
    predictions_root: Path,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    split_plan = read_json(split_plan_path)
    csv_rows = read_csv_rows(csv_path)
    folds = split_plan.get("folds")
    if not isinstance(folds, list):
        folds = []
        failures.append("split_plan_json: folds is not a list")
    fold_mappings = [fold for fold in folds if isinstance(fold, Mapping)]
    if len(fold_mappings) != len(folds):
        failures.append("split_plan_json: one or more folds are not JSON objects")

    add_check(
        checks,
        failures,
        name="split_plan_files_exist",
        passed=split_plan_path.is_file() and csv_path.is_file(),
        evidence={"json": rel(split_plan_path, repo_root), "csv": rel(csv_path, repo_root)},
        failure="split plan JSON or CSV is missing",
    )
    scope_pairs = expected_pairs(expected_markets, expected_years)
    manifest_pairs = expected_pairs(
        [str(item) for item in split_plan.get("markets", [])],
        [int(item) for item in split_plan.get("years", [])],
    )
    add_check(
        checks,
        failures,
        name="scope_matches_objective",
        passed=(
            split_plan.get("profile") == expected_profile
            and split_plan.get("resolved_profile") == expected_resolved_profile
            and rel(resolve_path(repo_root, str(split_plan.get("input_root"))), repo_root) == expected_input_root
            and manifest_pairs == scope_pairs
        ),
        evidence={
            "profile": split_plan.get("profile"),
            "resolved_profile": split_plan.get("resolved_profile"),
            "input_root": split_plan.get("input_root"),
            "markets": split_plan.get("markets"),
            "years": split_plan.get("years"),
        },
        failure="split plan scope does not match expected profile/input root/market-years",
    )

    fold_count = int_value(split_plan.get("fold_count"))
    fold_counts_by_market = Counter(str(fold.get("market") or "") for fold in fold_mappings)
    expected_fold_counts = dict(sorted(fold_counts_by_market.items()))
    add_check(
        checks,
        failures,
        name="fold_counts_match_manifest_and_csv",
        passed=(
            fold_count == len(fold_mappings)
            and len(csv_rows) == len(fold_mappings)
            and dict(split_plan.get("fold_count_by_market") or {}) == expected_fold_counts
            and csv_fold_ids(csv_rows) == {fold_id(fold) for fold in fold_mappings}
        ),
        evidence={
            "manifest_fold_count": fold_count,
            "json_fold_count": len(fold_mappings),
            "csv_row_count": len(csv_rows),
            "fold_count_by_market": dict(split_plan.get("fold_count_by_market") or {}),
        },
        failure="fold counts, CSV rows, or fold IDs do not match",
    )

    fold_failures, fold_summary = check_folds(
        folds=fold_mappings,
        expected_purge_bars=expected_purge_bars,
        expected_embargo_bars=expected_embargo_bars,
    )
    add_check(
        checks,
        failures,
        name="fold_chronology_positive_rows_and_purge_embargo",
        passed=not fold_failures,
        evidence=fold_summary,
        failure="; ".join(fold_failures[:20]),
    )

    feature_gate = split_plan.get("feature_manifest_gate")
    feature_gate = feature_gate if isinstance(feature_gate, Mapping) else {}
    feature_manifest_path = resolve_path(repo_root, str(feature_gate.get("manifest_path") or ""))
    feature_manifest_hash_matches = (
        feature_manifest_path.is_file()
        and str(feature_gate.get("manifest_hash") or "") == file_sha256(feature_manifest_path)
    )
    add_check(
        checks,
        failures,
        name="feature_manifest_gate_evidence",
        passed=(
            feature_gate.get("status") == "PASS"
            and not feature_gate.get("failures")
            and feature_gate.get("expected_output_root") == expected_input_root
            and feature_gate.get("expected_resolved_profile") == expected_resolved_profile
            and feature_manifest_hash_matches
        ),
        evidence={
            "status": feature_gate.get("status"),
            "manifest_path": feature_gate.get("manifest_path"),
            "expected_output_root": feature_gate.get("expected_output_root"),
            "expected_resolved_profile": feature_gate.get("expected_resolved_profile"),
            "hash_matches": feature_manifest_hash_matches,
        },
        failure="feature manifest gate is missing, failed, wrong-root, wrong-profile, or hash-stale",
    )

    universe_evidence = split_plan.get("data_audit_universe")
    universe_evidence = universe_evidence if isinstance(universe_evidence, Mapping) else {}
    universe_path = resolve_path(repo_root, str(universe_evidence.get("path") or ""))
    universe_hash_matches = (
        universe_path.is_file()
        and str(universe_evidence.get("file_hash") or "") == file_sha256(universe_path)
    )
    universe_failures: list[str] = []
    if universe_path.is_file():
        universe = load_data_audit_universe(universe_path)
        for market, year in sorted(scope_pairs):
            failure = universe.require_usable(market, year, context="split-plan acceptance review")
            if failure is not None:
                universe_failures.append(failure)
    else:
        universe_failures.append("data-audit universe file missing")
    add_check(
        checks,
        failures,
        name="data_audit_universe_evidence",
        passed=(
            universe_hash_matches
            and universe_evidence.get("requires_usable_for_wfa") is True
            and dict(universe_evidence.get("status_counts") or {}) == {"usable": len(scope_pairs)}
            and not universe_failures
        ),
        evidence={
            "path": universe_evidence.get("path"),
            "hash_matches": universe_hash_matches,
            "status_counts": universe_evidence.get("status_counts"),
            "requires_usable_for_wfa": universe_evidence.get("requires_usable_for_wfa"),
            "universe_failures": universe_failures,
        },
        failure="data-audit universe is missing, hash-stale, not all usable, or not WFA-usable",
    )

    report_root = split_plan_path.parent
    allowed_paths = {
        split_plan_path,
        csv_path,
        json_out,
        md_out,
    }
    scope_failures, scope_evidence = validate_generated_scope(
        report_root=report_root,
        allowed_paths={path.resolve() for path in allowed_paths},
        repo_root=repo_root,
    )
    prediction_file_count = count_prediction_files(predictions_root)
    add_check(
        checks,
        failures,
        name="generated_artifact_scope",
        passed=not scope_failures and prediction_file_count == 0,
        evidence={**scope_evidence, "prediction_file_count": prediction_file_count},
        failure="; ".join(scope_failures) or "prediction files are present",
    )

    status = PASS_STATUS if not failures else FAIL_STATUS
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope": {
            "profile": expected_profile,
            "resolved_profile": expected_resolved_profile,
            "input_root": expected_input_root,
            "markets": expected_markets,
            "years": expected_years,
            "market_year_count": len(scope_pairs),
        },
        "summary": {
            "fold_count": len(fold_mappings),
            "fold_count_by_market": fold_summary.get("fold_count_by_market", {}),
            "min_train_rows_after_purge": fold_summary.get("min_train_rows_after_purge"),
            "min_test_rows": fold_summary.get("min_test_rows"),
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "prediction_file_count": prediction_file_count,
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "input_evidence": {
            "split_plan_json": rel(split_plan_path, repo_root),
            "split_plan_json_sha256": file_sha256(split_plan_path),
            "split_plan_csv": rel(csv_path, repo_root),
            "split_plan_csv_sha256": file_sha256(csv_path),
            "feature_manifest": rel(feature_manifest_path, repo_root) if feature_manifest_path else None,
            "data_audit_universe": rel(universe_path, repo_root) if universe_path else None,
            "predictions_root": rel(predictions_root, repo_root),
        },
        "non_approval": {
            "wfa_model_training": False,
            "prediction_generation": False,
            "provider_calls": False,
            "data_replacement": False,
            "cleanup_archive": False,
            "staging_commit_push": False,
            "paper_or_live_work": False,
        },
        "non_approval_text": NO_MUTATION_TEXT,
        "recommended_next_action": (
            "If this acceptance report remains PASS, the next separately approved bounded step is "
            "a report-only Phase 6/WFA runner preflight against the accepted split plan; no model "
            "training, predictions, provider calls, data replacement, commits, pushes, paper, or live work."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 5 Split-Plan Acceptance Review",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at UTC: `{report['generated_at_utc']}`",
        f"- Fold count: `{report['summary']['fold_count']}`",
        f"- Fold count by market: `{report['summary']['fold_count_by_market']}`",
        f"- Min train rows after purge: `{report['summary']['min_train_rows_after_purge']}`",
        f"- Min test rows: `{report['summary']['min_test_rows']}`",
        f"- Prediction files: `{report['summary']['prediction_file_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Failure |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        failure = str(check.get("failure") or "").replace("|", "\\|")
        lines.append(f"| `{check['name']}` | `{check['status']}` | {failure} |")
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            f"- {report['non_approval_text']}",
            "",
            "## Recommended Next Action",
            "",
            f"- {report['recommended_next_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], json_out: Path, md_out: Path) -> tuple[Path, Path]:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(report), encoding="utf-8")
    return json_out, md_out


def csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--split-plan", default=str(DEFAULT_SPLIT_PLAN))
    parser.add_argument("--csv-path", default=None)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out", default=None)
    parser.add_argument("--expected-profile", default=EXPECTED_PROFILE)
    parser.add_argument("--expected-resolved-profile", default=EXPECTED_RESOLVED_PROFILE)
    parser.add_argument("--expected-input-root", default=EXPECTED_INPUT_ROOT)
    parser.add_argument("--expected-markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--expected-years", default=",".join(str(year) for year in EXPECTED_YEARS))
    parser.add_argument("--expected-purge-bars", type=int, default=EXPECTED_PURGE_BARS)
    parser.add_argument("--expected-embargo-bars", type=int, default=EXPECTED_EMBARGO_BARS)
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    split_plan_path = resolve_path(repo_root, args.split_plan)
    csv_path = resolve_path(repo_root, args.csv_path or split_plan_path.with_suffix(".csv"))
    json_out = resolve_path(
        repo_root,
        args.json_out or split_plan_path.with_name("split_plan_acceptance_report.json"),
    )
    md_out = resolve_path(
        repo_root,
        args.md_out or split_plan_path.with_name("split_plan_acceptance_report.md"),
    )
    report = build_report(
        repo_root=repo_root,
        split_plan_path=split_plan_path,
        csv_path=csv_path,
        json_out=json_out,
        md_out=md_out,
        expected_profile=str(args.expected_profile),
        expected_resolved_profile=str(args.expected_resolved_profile),
        expected_input_root=str(args.expected_input_root).replace("\\", "/"),
        expected_markets=csv_strings(args.expected_markets),
        expected_years=csv_ints(args.expected_years),
        expected_purge_bars=int(args.expected_purge_bars),
        expected_embargo_bars=int(args.expected_embargo_bars),
        predictions_root=resolve_path(repo_root, args.predictions_root),
    )
    json_path, md_path = write_report(report, json_out, md_out)
    print(
        f"{STAGE} status={report['status']} failures={len(report['failures'])} "
        f"folds={report['summary']['fold_count']} json={rel(json_path, repo_root)} "
        f"md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
