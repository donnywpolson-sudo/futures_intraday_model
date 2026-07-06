#!/usr/bin/env python3
"""Report-only disposition for broad causal source-reference failures."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_READINESS = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_raw_source_readiness.json"
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_reference_disposition.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_reference_disposition.md"

EXPECTED_STAGE = "broad_causal_raw_source_readiness"
OUTPUT_STAGE = "broad_causal_source_reference_disposition"
EXPECTED_FAILED_PAIRS = {"SR3:2020", "SR1:2020"}

READY_STATUS = "ready_for_build_input_only"
SOURCE_REFERENCE_STATUS = "action_required_source_reference_failure"
DEFERRED_STATUS = "deferred_policy_review_not_checked"

MISSING_SOURCE_STATUS = "blocked_missing_current_source_artifact"
HASH_MISMATCH_STATUS = "blocked_current_source_hash_mismatch"
RECOVERED_RERUN_STATUS = "current_source_recovered_rerun_readiness_required"
INVALID_STATE_STATUS = "invalid_unexpected_readiness_state"
DISPOSITION_STATUSES = [
    MISSING_SOURCE_STATUS,
    HASH_MISMATCH_STATUS,
    RECOVERED_RERUN_STATUS,
    INVALID_STATE_STATUS,
]

HISTORICAL_EVIDENCE_PATHS = [
    Path("reports/data_reorg/data_inventory_before.json"),
    Path("reports/data_audit/final/quarantine_plan.md"),
    Path(
        "reports/phase2_readiness/"
        "sr1_sr3_2020_parent_candidate_after_restore_20260626/"
        "sr_front_contract_candidate_manifest.json"
    ),
]

NON_APPROVAL_TEXT = (
    "This report-only source-reference disposition does not approve broader "
    "modeling, build execution, source repair, source restore, policy exclusion, "
    "cleanup, metrics, predictions, config promotion, labels, features, WFA, "
    "production/live use, or model promotion."
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


def validate_readiness(
    readiness: dict[str, Any],
    *,
    expected_rows: int = 527,
    expected_checked_action_required: int = 461,
    expected_ready: int = 459,
    expected_source_reference_failures: int = 2,
    expected_deferred: int = 66,
    expected_failed_pairs: set[str] = EXPECTED_FAILED_PAIRS,
) -> list[dict[str, Any]]:
    summary = readiness.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("readiness report missing summary object")
    counts = summary.get("readiness_status_counts")
    if not isinstance(counts, dict):
        raise ValueError("readiness report missing summary.readiness_status_counts object")
    rows = readiness.get("rows")
    if not isinstance(rows, list):
        raise ValueError("readiness report missing rows list")

    failures: list[str] = []
    _require_equal(summary.get("stage"), EXPECTED_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), "ACTION_REQUIRED", "summary.status", failures)
    _require_equal(summary.get("expected_rows"), expected_rows, "summary.expected_rows", failures)
    _require_equal(
        summary.get("checked_action_required_rows"),
        expected_checked_action_required,
        "summary.checked_action_required_rows",
        failures,
    )
    _require_equal(counts.get(READY_STATUS), expected_ready, f"counts.{READY_STATUS}", failures)
    _require_equal(
        counts.get(SOURCE_REFERENCE_STATUS),
        expected_source_reference_failures,
        f"counts.{SOURCE_REFERENCE_STATUS}",
        failures,
    )
    _require_equal(counts.get(DEFERRED_STATUS), expected_deferred, f"counts.{DEFERRED_STATUS}", failures)
    for flag in (
        "data_mutation_performed",
        "build_approved",
        "broader_modeling_approved",
        "config_promotion_approved",
        "research_use_allowed",
    ):
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)

    failed_rows = [row for row in rows if row.get("readiness_status") == SOURCE_REFERENCE_STATUS]
    failed_pairs = {str(row.get("pair")) for row in failed_rows}
    _require_equal(failed_pairs, expected_failed_pairs, "source_reference_failed_pairs", failures)
    _require_equal(len(failed_rows), len(expected_failed_pairs), "source_reference_failed_row_count", failures)

    if failures:
        raise ValueError("readiness report invariant failure: " + "; ".join(failures))
    return failed_rows


def historical_evidence_for(
    *,
    repo_root: Path,
    source_file: str,
    historical_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for relative_path in historical_paths or HISTORICAL_EVIDENCE_PATHS:
        path = resolve_path(repo_root, relative_path)
        file_present = path.is_file()
        contains_source_path = False
        if file_present:
            contains_source_path = source_file in path.read_text(encoding="utf-8", errors="ignore")
        results.append(
            {
                "path": rel(path, repo_root),
                "file_present": file_present,
                "contains_source_path": contains_source_path,
                "historical_evidence_only": True,
            }
        )
    return results


def _source_reference(row: dict[str, Any]) -> dict[str, Any]:
    references = row.get("source_references")
    if not isinstance(references, list) or len(references) != 1:
        raise ValueError(f"{row.get('pair')} expected exactly one source reference")
    reference = references[0]
    if not isinstance(reference, dict):
        raise ValueError(f"{row.get('pair')} source reference must be an object")
    return reference


def disposition_for_row(
    *,
    repo_root: Path,
    row: dict[str, Any],
    historical_paths: list[Path] | None = None,
) -> dict[str, Any]:
    pair = str(row.get("pair"))
    reference = _source_reference(row)
    source_file = str(reference.get("source_file") or "")
    expected_sha256 = str(reference.get("expected_sha256") or "")
    source_path = resolve_path(repo_root, source_file)
    source_root = repo_root / "data" / "dbn" / "ohlcv_1m_parent"
    source_parent = source_path.parent
    source_file_present = source_path.is_file()
    actual_sha256 = sha256_file(source_path) if source_file_present else None
    hash_matches = (
        actual_sha256 is not None
        and bool(expected_sha256)
        and actual_sha256.lower() == expected_sha256.lower()
    )
    if not source_file_present:
        disposition_status = MISSING_SOURCE_STATUS
    elif not hash_matches:
        disposition_status = HASH_MISMATCH_STATUS
    else:
        disposition_status = RECOVERED_RERUN_STATUS

    return {
        "pair": pair,
        "market": row.get("market"),
        "year": row.get("year"),
        "readiness_status": row.get("readiness_status"),
        "disposition_status": disposition_status,
        "planned_input_raw_path": row.get("planned_input_raw_path"),
        "raw_parquet_sha256": row.get("raw_parquet_sha256"),
        "raw_parquet_row_count": row.get("raw_parquet_row_count"),
        "timestamp_min": row.get("timestamp_min"),
        "timestamp_max": row.get("timestamp_max"),
        "source_file": source_file,
        "expected_sha256": expected_sha256,
        "source_root_present": source_root.is_dir(),
        "source_parent_dir_present": source_parent.is_dir(),
        "source_file_present": source_file_present,
        "actual_sha256": actual_sha256,
        "current_source_hash_matches": hash_matches if source_file_present else None,
        "historical_evidence_only": True,
        "historical_evidence": historical_evidence_for(
            repo_root=repo_root,
            source_file=source_file,
            historical_paths=historical_paths,
        ),
        "blockers": _blockers(disposition_status, source_file),
    }


def _blockers(disposition_status: str, source_file: str) -> list[str]:
    if disposition_status == MISSING_SOURCE_STATUS:
        return [f"current source artifact missing: {source_file}"]
    if disposition_status == HASH_MISMATCH_STATUS:
        return [f"current source artifact hash mismatch: {source_file}"]
    if disposition_status == RECOVERED_RERUN_STATUS:
        return ["current source artifact recovered; rerun raw/source readiness before any build"]
    return ["unexpected disposition state"]


def build_report(
    *,
    repo_root: Path,
    readiness_path: Path,
    generated_at_utc: str | None = None,
    historical_paths: list[Path] | None = None,
    expected_rows: int = 527,
    expected_checked_action_required: int = 461,
    expected_ready: int = 459,
    expected_source_reference_failures: int = 2,
    expected_deferred: int = 66,
    expected_failed_pairs: set[str] = EXPECTED_FAILED_PAIRS,
) -> dict[str, Any]:
    readiness = read_json(readiness_path)
    failed_rows = validate_readiness(
        readiness,
        expected_rows=expected_rows,
        expected_checked_action_required=expected_checked_action_required,
        expected_ready=expected_ready,
        expected_source_reference_failures=expected_source_reference_failures,
        expected_deferred=expected_deferred,
        expected_failed_pairs=expected_failed_pairs,
    )
    rows = [
        disposition_for_row(
            repo_root=repo_root,
            row=row,
            historical_paths=historical_paths,
        )
        for row in sorted(failed_rows, key=lambda item: str(item.get("pair")))
    ]
    counts = {status: 0 for status in DISPOSITION_STATUSES}
    counts.update(Counter(str(row["disposition_status"]) for row in rows))
    all_recovered = rows and all(row["disposition_status"] == RECOVERED_RERUN_STATUS for row in rows)
    status = "RERUN_READINESS_REQUIRED" if all_recovered else "ACTION_REQUIRED"
    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": status,
            "input_readiness": rel(readiness_path, repo_root),
            "input_readiness_sha256": sha256_file(readiness_path),
            "generated_at_utc": generated_at_utc or utc_now(),
            "failed_pair_count": len(rows),
            "failed_pairs": [str(row["pair"]) for row in rows],
            "disposition_status_counts": counts,
            "data_access": "read_only_current_source_presence_hash_and_historical_report_text",
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "historical_evidence_only": True,
            "non_approval": NON_APPROVAL_TEXT,
        },
        "disposition_status_definitions": {
            MISSING_SOURCE_STATUS: "Current referenced source file is absent.",
            HASH_MISMATCH_STATUS: "Current referenced source file exists but hash does not match.",
            RECOVERED_RERUN_STATUS: (
                "Current referenced source file exists and hash matches; raw/source readiness must be rerun."
            ),
            INVALID_STATE_STATUS: "Input readiness state did not match expected fail-closed invariants.",
        },
        "historical_evidence_policy": (
            "Historical report references are evidence-only and are not canonical source, "
            "repair, restore, build, exclusion, modeling, or config-promotion approval."
        ),
        "rows": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    counts = summary["disposition_status_counts"]
    lines = [
        "# Broad Manifest 527 Source-Reference Disposition",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only disposition for the two broad raw source-reference failures.",
        f"- Status: `{summary['status']}`.",
        f"- Failed pairs: `{', '.join(summary['failed_pairs'])}`.",
        f"- Disposition status counts: `{json.dumps(counts, sort_keys=True)}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `build_approved`: false.",
        "- `restore_approved`: false.",
        "- `repair_approved`: false.",
        "- `exclusion_approved`: false.",
        "- `broader_modeling_approved`: false.",
        "- `config_promotion_approved`: false.",
        "- `research_use_allowed`: false.",
        "- `historical_evidence_only`: true.",
        "",
        "## Historical Evidence Policy",
        "",
        report["historical_evidence_policy"],
        "",
        "## Disposition Status Definitions",
        "",
    ]
    for status, meaning in report["disposition_status_definitions"].items():
        lines.append(f"- `{status}`: {meaning}")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| pair | disposition | source present | raw rows | blockers |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for row in report["rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['disposition_status']}` | "
            f"{str(row['source_file_present']).lower()} | "
            f"{row.get('raw_parquet_row_count') or ''} | "
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
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    readiness_path = resolve_path(repo_root, args.readiness)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, readiness_path=readiness_path)
    except ValueError as exc:
        print(f"FAIL broad_causal_source_reference_disposition: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_source_reference_disposition "
        f"status={summary['status']} "
        f"failed_pair_count={summary['failed_pair_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
