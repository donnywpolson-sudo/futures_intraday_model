#!/usr/bin/env python3
"""Build and validate the tracked Phase 1A acquisition request registry."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    EXPECTED_COMPRESSION,
    EXPECTED_ENCODING,
    batch_split_duration_for_chunk,
    canonical_json_hash,
    canonical_json_text,
)


DEFAULT_OUTPUT = ROOT / "manifests" / "phase1a_acquisition_registry.jsonl"
DEFAULT_PLANS_ROOTS = (ROOT / "reports",)
PLAN_PATTERNS = (
    "*download_plan*.json",
    "*plan_dry_run.json",
    "*resume_plan.json",
    "*cost_plan.json",
)
LEGACY_APPROVAL_ID = "legacy_unrecorded_approval"
CURRENT_HASH_TYPE = "post_transfer_artifact_sha256"
DEFAULT_PROVENANCE_STATUS = "post_transfer_hash_only"
DEFAULT_REPRODUCIBILITY_STATUS = "partially_reproducible"

REQUIRED_REGISTRY_FIELDS = [
    "request_id",
    "dataset",
    "schema",
    "symbol",
    "stype_in",
    "stype_out",
    "start",
    "end",
    "output_path",
    "request_timestamp",
    "approval_id",
    "plan_hash",
]


def repo_relative_path(path: Path, repo_root: Path = ROOT) -> str:
    resolved_root = repo_root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return path.as_posix()


def path_is_git_tracked(path: Path, repo_root: Path = ROOT) -> bool:
    relative = repo_relative_path(path, repo_root)
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def iter_plan_paths(roots: Iterable[Path]) -> list[Path]:
    paths: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for pattern in PLAN_PATTERNS:
            paths.update(path for path in root.rglob(pattern) if path.is_file())
    return sorted(paths)


def stable_plan_hash(plan: Mapping[str, Any]) -> str:
    if plan.get("plan_hash"):
        return str(plan["plan_hash"])
    ignored = {"generated_at", "run_id", "run_kind", "plan_hash"}
    return canonical_json_hash({key: value for key, value in plan.items() if key not in ignored})


def sidecar_manifest_for_output(output_path: str, repo_root: Path = ROOT) -> Path:
    path = Path(output_path)
    if not path.is_absolute():
        path = repo_root / path
    return path.with_name(path.name + ".manifest.json")


def current_sidecar_fields(output_path: str, repo_root: Path = ROOT) -> dict[str, Any]:
    manifest_path = sidecar_manifest_for_output(output_path, repo_root)
    payload = read_json_object(manifest_path)
    if payload is None:
        return {
            "current_file_manifest_path": repo_relative_path(manifest_path, repo_root),
            "current_file_sha256": None,
            "current_file_hash_type": CURRENT_HASH_TYPE,
            "dataset_version": None,
            "schema_version": None,
            "request_text": None,
            "original_filename": None,
            "original_file_sha256": None,
            "download_started_at": None,
            "download_completed_at": None,
            "transfer_history": [],
        }
    return {
        "current_file_manifest_path": repo_relative_path(manifest_path, repo_root),
        "current_file_sha256": payload.get("file_sha256"),
        "current_file_hash_type": CURRENT_HASH_TYPE,
        "manifest_provenance_status": payload.get("provenance_status"),
        "manifest_reproducibility_status": payload.get("reproducibility_status"),
        "dataset_version": payload.get("dataset_version"),
        "schema_version": payload.get("schema_version"),
        "request_text": payload.get("request_text"),
        "original_filename": payload.get("original_filename"),
        "original_file_sha256": payload.get("original_file_sha256"),
        "download_started_at": payload.get("download_started_at"),
        "download_completed_at": payload.get("download_completed_at"),
        "transfer_history": payload.get("transfer_history") or [],
    }


def request_id_for_row(row: Mapping[str, Any]) -> str:
    keys = [
        "dataset",
        "schema",
        "symbol",
        "stype_in",
        "stype_out",
        "start",
        "end",
        "output_path",
    ]
    return canonical_json_hash({key: row.get(key) for key in keys})[:24]


def request_text_from_task(task: Mapping[str, Any]) -> str:
    chunk = str(task.get("chunk") or "year")
    return canonical_json_text(
        {
            "dataset": str(task.get("dataset") or ""),
            "symbols": str(task.get("symbol") or ""),
            "schema": str(task.get("schema") or ""),
            "stype_in": str(task.get("stype_in") or ""),
            "stype_out": str(task.get("stype_out") or ""),
            "start": str(task.get("start") or ""),
            "end": str(task.get("end") or ""),
            "encoding": EXPECTED_ENCODING,
            "compression": EXPECTED_COMPRESSION,
            "delivery": "download",
            "split_duration": batch_split_duration_for_chunk(chunk),
        }
    )


def row_from_task(
    task: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    source_plan_tracked: bool,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    plan_hash = stable_plan_hash(plan)
    output_path = str(task.get("output_path") or "")
    sidecar = current_sidecar_fields(output_path, repo_root)
    sidecar["request_text"] = sidecar.get("request_text") or request_text_from_task(task)
    provenance_status = (
        "original_delivery_hash_recorded"
        if sidecar.get("original_file_sha256")
        else DEFAULT_PROVENANCE_STATUS
    )
    reproducibility_status = (
        "reproducible_with_recorded_original_hash"
        if sidecar.get("original_file_sha256")
        and sidecar.get("dataset_version")
        and sidecar.get("schema_version")
        else DEFAULT_REPRODUCIBILITY_STATUS
    )
    validity_status = (
        "valid_current_artifact_if_current_hash_matches"
        if sidecar.get("current_file_sha256")
        else "request_definition_only_current_artifact_not_verified"
    )
    row = {
        "request_id": "",
        "dataset": str(task.get("dataset") or ""),
        "schema": str(task.get("schema") or plan.get("schema") or ""),
        "product": str(task.get("product") or ""),
        "year": task.get("year"),
        "symbol": str(task.get("symbol") or ""),
        "stype_in": str(task.get("stype_in") or plan.get("stype_in") or ""),
        "stype_out": str(task.get("stype_out") or plan.get("stype_out") or ""),
        "start": str(task.get("start") or ""),
        "end": str(task.get("end") or ""),
        "output_path": output_path,
        "request_timestamp": str(plan.get("generated_at") or ""),
        "approval_id": str(plan.get("approval_id") or LEGACY_APPROVAL_ID),
        "plan_hash": plan_hash,
        "observed_plan_hashes": [plan_hash],
        "source_plan_path": repo_relative_path(plan_path, repo_root),
        "observed_source_plan_paths": [repo_relative_path(plan_path, repo_root)],
        "source_plan_tracked": source_plan_tracked,
        "source_plan_run_kind": plan.get("run_kind"),
        "source_plan_mode": plan.get("mode"),
        "source_plan_schema": plan.get("schema"),
        "source_plan_reports_root": plan.get("reports_root"),
        "provenance_status": provenance_status,
        "reproducibility_status": reproducibility_status,
        "validity_status": validity_status,
        "current_file_hash_interpretation": CURRENT_HASH_TYPE,
        "notes": (
            "Current hashes validate post-transfer local artifacts only unless "
            "original delivery fields are populated."
        ),
        **sidecar,
    }
    row["request_id"] = request_id_for_row(row)
    return row


def rows_from_plan_path(plan_path: Path, *, repo_root: Path = ROOT) -> list[dict[str, Any]]:
    plan = read_json_object(plan_path)
    if plan is None:
        return []
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return []
    tracked = path_is_git_tracked(plan_path, repo_root)
    rows = [
        row_from_task(
            task,
            plan=plan,
            plan_path=plan_path,
            source_plan_tracked=tracked,
            repo_root=repo_root,
        )
        for task in tasks
        if isinstance(task, Mapping)
    ]
    return rows


def validate_registry_row(row: Mapping[str, Any]) -> list[str]:
    failures = [
        f"missing {field}"
        for field in REQUIRED_REGISTRY_FIELDS
        if row.get(field) in (None, "")
    ]
    if row.get("provenance_status") == "post_transfer_hash_only":
        if row.get("reproducibility_status") != "partially_reproducible":
            failures.append("post_transfer_hash_only row must be partially_reproducible")
    if row.get("validity_status") == "invalid":
        failures.append("registry must not mark existing files invalid solely for missing provenance")
    return failures


def _merge_duplicate_row(existing: dict[str, Any], new: Mapping[str, Any]) -> None:
    existing_hashes = set(existing.get("observed_plan_hashes") or [])
    existing_hashes.add(str(new.get("plan_hash")))
    for plan_hash in new.get("observed_plan_hashes") or []:
        existing_hashes.add(str(plan_hash))
    existing["observed_plan_hashes"] = sorted(hash_value for hash_value in existing_hashes if hash_value)

    existing_paths = set(existing.get("observed_source_plan_paths") or [])
    if new.get("source_plan_path"):
        existing_paths.add(str(new["source_plan_path"]))
    for source_path in new.get("observed_source_plan_paths") or []:
        existing_paths.add(str(source_path))
    existing["observed_source_plan_paths"] = sorted(path for path in existing_paths if path)

    existing_was_tracked = bool(existing.get("source_plan_tracked"))
    new_is_tracked = bool(new.get("source_plan_tracked"))
    existing["source_plan_tracked"] = existing_was_tracked or new_is_tracked
    if existing.get("approval_id") == LEGACY_APPROVAL_ID and new.get("approval_id") != LEGACY_APPROVAL_ID:
        existing["approval_id"] = new.get("approval_id")
    if not existing_was_tracked and new_is_tracked:
        existing["source_plan_path"] = new.get("source_plan_path")
        existing["plan_hash"] = new.get("plan_hash")

    timestamps = [
        str(value)
        for value in [
            existing.get("request_timestamp"),
            existing.get("latest_request_timestamp"),
            new.get("request_timestamp"),
        ]
        if value
    ]
    if timestamps:
        existing["request_timestamp"] = min(timestamps)
        existing["latest_request_timestamp"] = max(timestamps)


def dedupe_and_sort_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_request_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        request_id = str(row.get("request_id"))
        if request_id in by_request_id:
            _merge_duplicate_row(by_request_id[request_id], row)
        else:
            row["latest_request_timestamp"] = row.get("request_timestamp")
            by_request_id[request_id] = row
    return sorted(
        by_request_id.values(),
        key=lambda row: (
            str(row.get("dataset")),
            str(row.get("schema")),
            str(row.get("symbol")),
            str(row.get("start")),
            str(row.get("end")),
            str(row.get("output_path")),
            str(row.get("plan_hash")),
        ),
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def build_registry(plan_roots: Iterable[Path], *, repo_root: Path = ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plan_path in iter_plan_paths(plan_roots):
        rows.extend(rows_from_plan_path(plan_path, repo_root=repo_root))
    return dedupe_and_sort_rows(rows)


def validation_failures(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        for failure in validate_registry_row(row):
            failures.append(f"row {index} {row.get('request_id')}: {failure}")
    return failures


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plans-root",
        action="append",
        default=None,
        help="Root to scan for Databento request plans; may be passed multiple times.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    output = Path(args.output)
    if args.validate_only:
        rows = read_jsonl(output)
    else:
        roots = [Path(item) for item in args.plans_root] if args.plans_root else list(DEFAULT_PLANS_ROOTS)
        rows = build_registry(roots)
        write_jsonl(output, rows)
    failures = validation_failures(rows)
    print(f"PHASE1A_ACQUISITION_REGISTRY rows={len(rows)} failures={len(failures)} output={output.as_posix()}")
    for failure in failures[:50]:
        print(f"FAIL {failure}")
    if len(failures) > 50:
        print(f"FAIL additional_failures={len(failures) - 50}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
