#!/usr/bin/env python3
"""Read-only PIT inventory gate for optional metadata in the 460-row canonical scope."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation.feature_leakage_guard import forbidden_feature_columns


CLASS_FEATURE_ALLOWED = "feature_allowed_candidate"
CLASS_AUDIT_ONLY = "audit_only"
CLASS_PIT_NOT_VERIFIED = "pit_not_verified"
CLASS_FORBIDDEN_FEATURE = "forbidden_feature"
CLASS_SOURCE_LINEAGE = "source_lineage"
CLASS_UNCLASSIFIED = "unclassified"
CLASSIFICATIONS = {
    CLASS_FEATURE_ALLOWED,
    CLASS_AUDIT_ONLY,
    CLASS_PIT_NOT_VERIFIED,
    CLASS_FORBIDDEN_FEATURE,
    CLASS_SOURCE_LINEAGE,
}

STATUS_GO = "CONDITIONAL_GO_OPTIONAL_METADATA_PIT_INVENTORY_460_ONLY"
STATUS_NO_GO = "NO_GO_OPTIONAL_METADATA_PIT_INVENTORY"
WARN_OPTIONAL_METADATA_BLOCKED = "WARN_OPTIONAL_METADATA_BLOCKED"

SOURCE_LINEAGE_COLUMNS = {
    "source_path",
    "source_file",
    "source_sha256",
    "source_file_hash",
    "source_row_number",
    "definition_source_file",
    "definition_source_sha256",
    "status_source_file",
    "status_source_sha256",
    "timestamp_source",
}
SOURCE_LINEAGE_SUFFIXES = ("_source_file", "_source_sha256", "_source_hash", "_path")
OPTIONAL_METADATA_PREFIXES = ("status_", "stat_", "statistics_")
OPTIONAL_METADATA_TERMS = ("settlement", "open_interest", "cleared_volume")
ROLL_COLUMNS = {
    "roll_boundary_flag",
    "bars_since_roll",
    "bars_until_roll",
    "roll_window_flag",
    "roll_detection_available",
    "roll_detection_source",
    "roll_policy_status",
}
AUDIT_ONLY_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "session_calendar_status",
    "holiday_calendar_available",
    "early_close_calendar_available",
    "calendar_coverage_status",
    "session_template",
    "is_session_open",
    "is_session_close",
    "minutes_since_session_open",
    "minutes_until_session_close",
    "session_progress",
    "minute_of_day",
    "day_of_week",
    "metadata_available",
}


def _parquet_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.parquet"))


def _schema_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema_arrow.names)


def _load_default_feature_cols(feature_cols: Iterable[str] | None) -> list[str]:
    if feature_cols is not None:
        return list(feature_cols)
    from scripts.phase4_features.build_baseline_features import FEATURE_COLS

    return list(FEATURE_COLS)


def classify_column(column: str, feature_cols: set[str]) -> str:
    if column in SOURCE_LINEAGE_COLUMNS or column.endswith(SOURCE_LINEAGE_SUFFIXES):
        return CLASS_SOURCE_LINEAGE
    if column.startswith(OPTIONAL_METADATA_PREFIXES) or any(term in column for term in OPTIONAL_METADATA_TERMS):
        return CLASS_PIT_NOT_VERIFIED
    if column in ROLL_COLUMNS or column.startswith(("target_", "future_")):
        return CLASS_FORBIDDEN_FEATURE
    if forbidden_feature_columns([column]):
        return CLASS_FORBIDDEN_FEATURE
    if column.startswith("feature_"):
        return CLASS_FEATURE_ALLOWED if column in feature_cols else CLASS_AUDIT_ONLY
    if column in AUDIT_ONLY_COLUMNS:
        return CLASS_AUDIT_ONLY
    return CLASS_UNCLASSIFIED


def classify_columns(columns: Iterable[str], feature_cols: Iterable[str]) -> dict[str, str]:
    feature_col_set = set(feature_cols)
    return {column: classify_column(column, feature_col_set) for column in sorted(set(columns))}


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


def evaluate_inventory(
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
    current_features = _load_default_feature_cols(feature_cols)
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
        feature_cols=current_features,
        git_head=git_head,
        staged_names=staged_names,
        scoped_status_lines=scoped_status_lines,
        generated_at_utc=generated_at_utc,
    )
    parquet_paths = _parquet_paths(canonical_root)
    columns_by_file: dict[str, list[str]] = {}
    all_columns: set[str] = set()
    schema_failures: list[str] = []
    for path in parquet_paths:
        try:
            columns = _schema_columns(path)
        except Exception as exc:
            schema_failures.append(f"{scope_gate.rel(path, repo_root)}: {type(exc).__name__}: {exc}")
            continue
        columns_by_file[scope_gate.rel(path, repo_root)] = columns
        all_columns.update(columns)

    classifications = classify_columns(all_columns, current_features)
    class_counts = Counter(classifications.values())
    unclassified = sorted(
        column for column, classification in classifications.items() if classification == CLASS_UNCLASSIFIED
    )
    forbidden_features = forbidden_feature_columns(current_features)
    blocked_feature_columns = sorted(
        column
        for column in current_features
        if classify_column(column, set(current_features))
        in {CLASS_PIT_NOT_VERIFIED, CLASS_FORBIDDEN_FEATURE, CLASS_SOURCE_LINEAGE}
        or forbidden_feature_columns([column])
    )

    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _check(
        checks,
        name="scope_gate_passed",
        passed=scope_report["summary"]["status"] == scope_gate.STATUS_GO,
        observed=scope_report["summary"]["status"],
        expected=scope_gate.STATUS_GO,
        detail="Optional metadata PIT inventory is valid only for the approved 460-row canonical scope.",
    )
    _check(
        checks,
        name="schema_read_success",
        passed=not schema_failures,
        observed=schema_failures[:20],
        expected=[],
        detail="All canonical parquet schemas must be readable via parquet metadata.",
    )
    _check(
        checks,
        name="all_columns_classified",
        passed=not unclassified,
        observed=unclassified,
        expected=[],
        detail="Every discovered canonical column must map to one PIT inventory classification.",
    )
    _check(
        checks,
        name="feature_registry_no_forbidden_columns",
        passed=not forbidden_features and not blocked_feature_columns,
        observed={"forbidden": forbidden_features, "blocked": blocked_feature_columns},
        expected={"forbidden": [], "blocked": []},
        detail="Baseline feature columns must not include PIT-not-verified, forbidden, or source-lineage columns.",
    )
    _check(
        checks,
        name="required_pit_metadata_detected",
        passed=class_counts[CLASS_PIT_NOT_VERIFIED] > 0,
        observed=class_counts[CLASS_PIT_NOT_VERIFIED],
        expected="> 0",
        detail="The gate must detect optional metadata columns and keep them blocked from features.",
    )
    if class_counts[CLASS_PIT_NOT_VERIFIED] > 0:
        _warn(
            warnings,
            name="pit_not_verified_columns_present",
            code=WARN_OPTIONAL_METADATA_BLOCKED,
            observed=class_counts[CLASS_PIT_NOT_VERIFIED],
            expected="blocked until available_at <= decision_time proof exists",
            detail="Optional status/statistics/settlement/open-interest/cleared-volume metadata remains audit-only.",
        )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_GO if not failures else STATUS_NO_GO
    return {
        "summary": {
            "stage": "optional_metadata_pit_inventory",
            "generated_at_utc": generated_at_utc or scope_gate.utc_now(),
            "status": status,
            "approved_scope": "promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2 only",
            "canonical_root": scope_gate.rel(canonical_root, repo_root),
            "canonical_parquet_count": len(parquet_paths),
            "expected_count": expected_count,
            "column_count": len(classifications),
            "classification_counts": dict(sorted(class_counts.items())),
            "pit_not_verified_count": class_counts[CLASS_PIT_NOT_VERIFIED],
            "source_lineage_count": class_counts[CLASS_SOURCE_LINEAGE],
            "forbidden_feature_count": class_counts[CLASS_FORBIDDEN_FEATURE],
            "feature_allowed_candidate_count": class_counts[CLASS_FEATURE_ALLOWED],
            "audit_only_count": class_counts[CLASS_AUDIT_ONLY],
            "unclassified_count": len(unclassified),
            "feature_column_count": len(current_features),
            "blocked_feature_column_count": len(blocked_feature_columns),
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
        "classifications": classifications,
        "unclassified_columns": unclassified,
        "blocked_feature_columns": blocked_feature_columns,
        "schema_failures": schema_failures,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "optional_metadata_pit_inventory "
        f"status={summary['status']} "
        f"canonical_parquet_count={summary['canonical_parquet_count']}/{summary['expected_count']} "
        f"column_count={summary['column_count']} "
        f"pit_not_verified={summary['pit_not_verified_count']} "
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
    report = evaluate_inventory(
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
