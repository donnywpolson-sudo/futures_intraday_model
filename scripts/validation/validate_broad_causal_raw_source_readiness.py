#!/usr/bin/env python3
"""Report-only raw/source/hash readiness validator for the broad causal rebuild."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_PREBUILD_PLAN = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_prebuild_plan.json"
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_raw_source_readiness.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_raw_source_readiness.md"

EXPECTED_STAGE = "broad_causal_rebuild_prebuild_plan"
OUTPUT_STAGE = "broad_causal_raw_source_readiness"
FUTURE_ROOT = "data/causally_gated_normalized"
EXPECTED_ROW_COUNT = 527
EXPECTED_ACTION_REQUIRED = 461
EXPECTED_DEFERRED_POLICY_REVIEW = 66

REQUIRED_RAW_COLUMNS = [
    "ts_event",
    "market",
    "year",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source_file",
    "source_sha256",
]
READ_COLUMNS = ["ts_event", "market", "year", "source_file", "source_sha256"]

READY_STATUS = "ready_for_build_input_only"
MISSING_RAW_STATUS = "action_required_missing_raw"
UNREADABLE_RAW_STATUS = "action_required_unreadable_raw"
SCHEMA_OR_METADATA_STATUS = "action_required_schema_or_metadata_failure"
SOURCE_REFERENCE_STATUS = "action_required_source_reference_failure"
DEFERRED_STATUS = "deferred_policy_review_not_checked"
EXCLUDED_STATUS = "excluded_from_phase2_not_checked"
READINESS_STATUSES = [
    READY_STATUS,
    MISSING_RAW_STATUS,
    UNREADABLE_RAW_STATUS,
    SCHEMA_OR_METADATA_STATUS,
    SOURCE_REFERENCE_STATUS,
    DEFERRED_STATUS,
    EXCLUDED_STATUS,
]

NON_APPROVAL_TEXT = (
    "This report-only raw/source/hash readiness validation does not approve broader "
    "modeling, cleanup, metrics, predictions, config promotion, labels, features, "
    "WFA, production/live use, model promotion, or build execution."
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


def _require_equal(actual: Any, expected: Any, label: str, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label}={actual!r}, expected {expected!r}")


def validate_prebuild_plan(
    plan: dict[str, Any],
    *,
    expected_rows: int = EXPECTED_ROW_COUNT,
    expected_action_required: int = EXPECTED_ACTION_REQUIRED,
    expected_deferred_policy_review: int = EXPECTED_DEFERRED_POLICY_REVIEW,
) -> list[dict[str, Any]]:
    summary = plan.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("prebuild plan missing summary object")
    counts = summary.get("status_counts")
    if not isinstance(counts, dict):
        raise ValueError("prebuild plan missing summary.status_counts object")

    failures: list[str] = []
    _require_equal(summary.get("stage"), EXPECTED_STAGE, "summary.stage", failures)
    _require_equal(summary.get("future_root"), FUTURE_ROOT, "summary.future_root", failures)
    _require_equal(summary.get("expected_rows"), expected_rows, "summary.expected_rows", failures)
    _require_equal(
        counts.get("action_required"),
        expected_action_required,
        "summary.status_counts.action_required",
        failures,
    )
    _require_equal(
        counts.get("deferred_policy_review"),
        expected_deferred_policy_review,
        "summary.status_counts.deferred_policy_review",
        failures,
    )
    for flag in (
        "broader_modeling_approved",
        "config_promotion_approved",
        "legacy_restore_approved",
        "research_use_allowed",
    ):
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)

    rows = plan.get("rows")
    if not isinstance(rows, list):
        failures.append("rows missing or not a list")
    elif len(rows) != expected_rows:
        failures.append(f"rows length={len(rows)!r}, expected {expected_rows!r}")

    if failures:
        raise ValueError("prebuild plan invariant failure: " + "; ".join(failures))
    return rows


def _split_source_values(value: object) -> list[str]:
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _timestamp_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _unique_text_values(series: pd.Series) -> list[str]:
    return sorted(str(value) for value in series.dropna().unique().tolist())


def _unique_int_values(series: pd.Series) -> list[int]:
    values = pd.to_numeric(series, errors="coerce").dropna().astype("int64").unique().tolist()
    return sorted(int(value) for value in values)


def _source_reference_report(
    *,
    frame: pd.DataFrame,
    repo_root: Path,
    hash_cache: dict[Path, str],
) -> tuple[list[dict[str, Any]], list[str], int]:
    references: list[dict[str, Any]] = []
    failures: list[str] = []
    reference_count = 0
    distinct = frame[["source_file", "source_sha256"]].drop_duplicates()
    for _, row in distinct.iterrows():
        source_files = _split_source_values(row["source_file"])
        source_hashes = _split_source_values(row["source_sha256"])
        if not source_files:
            continue
        reference_count += len(source_files)
        if not source_hashes:
            failures.append("source_file has non-null path without source_sha256")
            references.append(
                {
                    "source_file": str(row["source_file"]),
                    "expected_sha256": None,
                    "actual_sha256": None,
                    "hash_matches": False,
                    "source_present": None,
                }
            )
            continue
        if len(source_files) != len(source_hashes):
            failures.append("source_file/source_sha256 reference count mismatch")
            references.append(
                {
                    "source_file": str(row["source_file"]),
                    "expected_sha256": str(row["source_sha256"]),
                    "actual_sha256": None,
                    "hash_matches": False,
                    "source_present": None,
                }
            )
            continue
        for source_file, expected_hash in zip(source_files, source_hashes, strict=True):
            source_path = resolve_path(repo_root, source_file)
            source_present = source_path.is_file()
            actual_hash = None
            hash_matches = False
            if not source_present:
                failures.append(f"source file missing: {source_file}")
            else:
                actual_hash = hash_cache.get(source_path)
                if actual_hash is None:
                    actual_hash = sha256_file(source_path)
                    hash_cache[source_path] = actual_hash
                hash_matches = actual_hash.lower() == expected_hash.lower()
                if not hash_matches:
                    failures.append(f"source hash mismatch: {source_file}")
            references.append(
                {
                    "source_file": source_file,
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "hash_matches": hash_matches,
                    "source_present": source_present,
                }
            )
    if reference_count == 0:
        failures.append("source_file/source_sha256 references absent")
    return references, failures, reference_count


def _status_from_failures(
    *,
    missing_raw: bool,
    unreadable_failures: list[str],
    schema_failures: list[str],
    source_failures: list[str],
) -> str:
    if missing_raw:
        return MISSING_RAW_STATUS
    if unreadable_failures:
        return UNREADABLE_RAW_STATUS
    if source_failures:
        return SOURCE_REFERENCE_STATUS
    if schema_failures:
        return SCHEMA_OR_METADATA_STATUS
    return READY_STATUS


def validate_action_required_row(
    *,
    repo_root: Path,
    row: dict[str, Any],
    hash_cache: dict[Path, str],
) -> dict[str, Any]:
    raw_path_text = str(row.get("planned_input_raw_path") or "")
    raw_path = resolve_path(repo_root, raw_path_text)
    market = str(row.get("market"))
    year = int(row.get("year"))
    raw_present = raw_path.is_file()
    unreadable_failures: list[str] = []
    schema_failures: list[str] = []
    source_failures: list[str] = []
    source_references: list[dict[str, Any]] = []

    evidence: dict[str, Any] = {
        "market": market,
        "year": year,
        "pair": row.get("pair") or f"{market}:{year}",
        "planned_input_raw_path": raw_path_text,
        "planned_output_causal_path": row.get("planned_output_causal_path"),
        "prebuild_status": row.get("prebuild_status"),
        "raw_read_performed": raw_present,
        "raw_path_present": raw_present,
        "raw_parquet_sha256": None,
        "raw_parquet_row_count": None,
        "raw_column_count": None,
        "required_columns_missing": [],
        "timestamp_min": None,
        "timestamp_max": None,
        "timestamp_null_count": None,
        "market_values": [],
        "year_values": [],
        "source_reference_count": 0,
        "source_references": source_references,
        "blockers": [],
    }

    if not raw_present:
        evidence["readiness_status"] = MISSING_RAW_STATUS
        evidence["blockers"] = [f"missing raw parquet: {raw_path_text}"]
        return evidence

    try:
        evidence["raw_parquet_sha256"] = sha256_file(raw_path)
        parquet = pq.ParquetFile(raw_path)
        columns = list(parquet.schema_arrow.names)
        evidence["raw_parquet_row_count"] = int(parquet.metadata.num_rows)
        evidence["raw_column_count"] = len(columns)
    except Exception as exc:  # noqa: BLE001 - report-only audit must fail closed.
        unreadable_failures.append(f"unreadable raw parquet metadata/hash: {exc}")
        evidence["readiness_status"] = UNREADABLE_RAW_STATUS
        evidence["blockers"] = unreadable_failures
        return evidence

    missing_columns = sorted(set(REQUIRED_RAW_COLUMNS) - set(columns))
    evidence["required_columns_missing"] = missing_columns
    if missing_columns:
        schema_failures.append("missing required raw columns: " + ",".join(missing_columns))
    if int(evidence["raw_parquet_row_count"] or 0) <= 0:
        schema_failures.append("raw parquet has no rows")

    if not missing_columns:
        try:
            frame = pd.read_parquet(raw_path, columns=READ_COLUMNS)
        except Exception as exc:  # noqa: BLE001 - report-only audit must fail closed.
            unreadable_failures.append(f"unreadable raw parquet selected columns: {exc}")
        else:
            timestamps = pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
            valid_timestamps = timestamps.dropna()
            evidence["timestamp_min"] = _timestamp_text(valid_timestamps.min()) if not valid_timestamps.empty else None
            evidence["timestamp_max"] = _timestamp_text(valid_timestamps.max()) if not valid_timestamps.empty else None
            evidence["timestamp_null_count"] = int(timestamps.isna().sum())
            if valid_timestamps.empty:
                schema_failures.append("ts_event has no valid timestamps")

            market_values = _unique_text_values(frame["market"])
            year_values = _unique_int_values(frame["year"])
            evidence["market_values"] = market_values
            evidence["year_values"] = year_values
            if market_values != [market]:
                schema_failures.append(f"market column values {market_values!r} do not equal {market!r}")
            if year_values != [year]:
                schema_failures.append(f"year column values {year_values!r} do not equal {year!r}")

            source_references, source_failures, reference_count = _source_reference_report(
                frame=frame,
                repo_root=repo_root,
                hash_cache=hash_cache,
            )
            evidence["source_references"] = source_references
            evidence["source_reference_count"] = reference_count

    status = _status_from_failures(
        missing_raw=False,
        unreadable_failures=unreadable_failures,
        schema_failures=schema_failures,
        source_failures=source_failures,
    )
    evidence["readiness_status"] = status
    evidence["blockers"] = unreadable_failures + source_failures + schema_failures
    return evidence


def carry_not_checked_row(row: dict[str, Any], readiness_status: str) -> dict[str, Any]:
    market = str(row.get("market"))
    year = int(row.get("year"))
    return {
        "market": market,
        "year": year,
        "pair": row.get("pair") or f"{market}:{year}",
        "planned_input_raw_path": row.get("planned_input_raw_path"),
        "planned_output_causal_path": row.get("planned_output_causal_path"),
        "prebuild_status": row.get("prebuild_status"),
        "readiness_status": readiness_status,
        "raw_read_performed": False,
        "raw_path_present": None,
        "raw_parquet_sha256": None,
        "raw_parquet_row_count": None,
        "raw_column_count": None,
        "required_columns_missing": [],
        "timestamp_min": None,
        "timestamp_max": None,
        "timestamp_null_count": None,
        "market_values": [],
        "year_values": [],
        "source_reference_count": 0,
        "source_references": [],
        "blockers": ["row remains non-research until separately approved"],
    }


def build_report(
    *,
    repo_root: Path,
    prebuild_plan_path: Path,
    generated_at_utc: str | None = None,
    expected_rows: int = EXPECTED_ROW_COUNT,
    expected_action_required: int = EXPECTED_ACTION_REQUIRED,
    expected_deferred_policy_review: int = EXPECTED_DEFERRED_POLICY_REVIEW,
) -> dict[str, Any]:
    prebuild_plan = read_json(prebuild_plan_path)
    rows = validate_prebuild_plan(
        prebuild_plan,
        expected_rows=expected_rows,
        expected_action_required=expected_action_required,
        expected_deferred_policy_review=expected_deferred_policy_review,
    )

    hash_cache: dict[Path, str] = {}
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        prebuild_status = str(row.get("prebuild_status") or "")
        if prebuild_status == "action_required":
            output_rows.append(
                validate_action_required_row(repo_root=repo_root, row=row, hash_cache=hash_cache)
            )
        elif prebuild_status == "deferred_policy_review":
            output_rows.append(carry_not_checked_row(row, DEFERRED_STATUS))
        elif prebuild_status == "excluded_from_phase2":
            output_rows.append(carry_not_checked_row(row, EXCLUDED_STATUS))
        else:
            raise ValueError(f"unsupported prebuild_status for {row.get('pair')}: {prebuild_status!r}")

    counts = {status: 0 for status in READINESS_STATUSES}
    counts.update(Counter(str(row["readiness_status"]) for row in output_rows))
    ready_count = counts[READY_STATUS]
    checked_action_required = sum(1 for row in output_rows if row["prebuild_status"] == "action_required")
    all_action_required_ready = checked_action_required == ready_count
    report_status = "READY_FOR_SEPARATE_BUILD_APPROVAL" if all_action_required_ready else "ACTION_REQUIRED"

    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": report_status,
            "future_root": FUTURE_ROOT,
            "expected_rows": len(output_rows),
            "checked_action_required_rows": checked_action_required,
            "deferred_policy_review_rows": counts[DEFERRED_STATUS],
            "readiness_status_counts": counts,
            "input_prebuild_plan": rel(prebuild_plan_path, repo_root),
            "input_prebuild_plan_sha256": sha256_file(prebuild_plan_path),
            "generated_at_utc": generated_at_utc or utc_now(),
            "data_access": "read_only_raw_and_source_files_no_data_mutation",
            "data_mutation_performed": False,
            "build_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "non_approval": NON_APPROVAL_TEXT,
        },
        "required_raw_columns": REQUIRED_RAW_COLUMNS,
        "readiness_status_definitions": {
            READY_STATUS: (
                "Input raw/source/hash checks passed for a prebuild action_required row; "
                "this is not build, modeling, or config-promotion approval."
            ),
            MISSING_RAW_STATUS: "Planned raw parquet is absent.",
            UNREADABLE_RAW_STATUS: "Raw parquet metadata or selected columns could not be read.",
            SCHEMA_OR_METADATA_STATUS: (
                "Raw schema, row count, timestamp bounds, or market/year consistency failed."
            ),
            SOURCE_REFERENCE_STATUS: (
                "source_file/source_sha256 references are absent, missing, mismatched, or hash-invalid."
            ),
            DEFERRED_STATUS: "Policy-deferred row was not checked and remains non-research.",
            EXCLUDED_STATUS: "Explicitly excluded row was not checked.",
        },
        "rows": output_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    counts = summary["readiness_status_counts"]
    lines = [
        "# Broad Manifest 527 Raw/Source/Hash Readiness",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only raw/source/hash readiness validation.",
        f"- Status: `{summary['status']}`.",
        f"- Future root: `{summary['future_root']}`.",
        f"- Expected rows: {summary['expected_rows']}.",
        f"- Checked action-required rows: {summary['checked_action_required_rows']}.",
        f"- Deferred policy-review rows: {summary['deferred_policy_review_rows']}.",
        f"- Readiness status counts: `{json.dumps(counts, sort_keys=True)}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `build_approved`: false.",
        "- `broader_modeling_approved`: false.",
        "- `config_promotion_approved`: false.",
        "- `research_use_allowed`: false.",
        "",
        "## Required Raw Columns",
        "",
        *[f"- `{column}`" for column in report["required_raw_columns"]],
        "",
        "## Readiness Status Definitions",
        "",
    ]
    for status, meaning in report["readiness_status_definitions"].items():
        lines.append(f"- `{status}`: {meaning}")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| pair | readiness status | raw rows | blockers |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in report["rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        raw_rows = row.get("raw_parquet_row_count")
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['readiness_status']}` | "
            f"{'' if raw_rows is None else raw_rows} | "
            f"{blockers} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--prebuild-plan", default=str(DEFAULT_PREBUILD_PLAN))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    prebuild_plan = resolve_path(repo_root, args.prebuild_plan)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, prebuild_plan_path=prebuild_plan)
    except ValueError as exc:
        print(f"FAIL broad_causal_raw_source_readiness: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_raw_source_readiness "
        f"status={summary['status']} "
        f"expected_rows={summary['expected_rows']} "
        f"checked_action_required_rows={summary['checked_action_required_rows']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
