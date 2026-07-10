#!/usr/bin/env python3
"""Build a Phase 8 execution-realism evidence report from local source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REQUIRED_CATEGORIES = {
    "delay_stress": "execution delay stress",
    "liquidity_window": "execution liquidity window",
    "spread_slippage": "execution spread/slippage",
    "partial_fills_rejects": "execution partial fills/rejects",
}
REVIEWED_STATUSES = {"PASS", "FAIL"}
SUMMARY_NAME = "execution_realism_summary.json"
INVENTORY_NAME = "execution_realism_source_inventory.json"
README_NAME = "execution_realism_summary.md"


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() and path.is_file() else "MISSING"


def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve(strict=False)
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_rows(source_manifest: Any) -> list[Mapping[str, Any]]:
    if isinstance(source_manifest, list):
        rows = source_manifest
    elif isinstance(source_manifest, Mapping):
        rows = (
            source_manifest.get("sources")
            or source_manifest.get("source_files")
            or source_manifest.get("evidence_sources")
            or []
        )
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping)]


def _normalize_status(value: object) -> str:
    return str(value or "").strip().upper()


def _review_rationale(row: Mapping[str, Any]) -> str:
    value = row.get("review_rationale", row.get("rationale"))
    return str(value or "").strip()


def _resolve_source_path(row_path: object, *, source_manifest_path: Path) -> Path | None:
    if not isinstance(row_path, str) or not row_path.strip():
        return None
    path = Path(row_path).expanduser()
    return path if path.is_absolute() else source_manifest_path.parent / path


def _base_inventory_row(
    *,
    index: int,
    row: Mapping[str, Any],
    source_manifest_path: Path,
) -> dict[str, Any]:
    category = str(row.get("category") or "").strip()
    description = str(row.get("description") or "").strip()
    review_status = _normalize_status(row.get("review_status"))
    rationale = _review_rationale(row)
    source_path = _resolve_source_path(row.get("path"), source_manifest_path=source_manifest_path)
    normalized_source_path = _display_path(source_path) if source_path is not None else None
    exists = bool(source_path and source_path.exists())
    is_file = bool(source_path and source_path.is_file())
    size_bytes: int | None = None
    stat_error: str | None = None
    if source_path is not None and exists and is_file:
        try:
            size_bytes = int(source_path.stat().st_size)
        except OSError as exc:
            stat_error = str(exc)
    return {
        "index": index,
        "category": category,
        "description": description,
        "review_status": review_status or None,
        "review_rationale": rationale or None,
        "source_path": normalized_source_path,
        "exists": exists,
        "is_file": is_file,
        "size_bytes": size_bytes,
        "stat_error": stat_error,
        "status": "PENDING",
        "reason": "pending source inspection",
    }


def _finalize_inventory_row(
    row: dict[str, Any],
    *,
    source_manifest_path: Path,
    budget_failure: str | None,
) -> dict[str, Any]:
    category = str(row.get("category") or "")
    description = str(row.get("description") or "")
    review_status = str(row.get("review_status") or "")
    rationale = str(row.get("review_rationale") or "")
    source_path = _resolve_source_path(row.get("source_path"), source_manifest_path=Path.cwd())
    reasons: list[str] = []
    source_hash: str | None = None
    if budget_failure:
        reasons.append(budget_failure)
    if category not in REQUIRED_CATEGORIES:
        reasons.append("category missing or unsupported")
    if not description:
        reasons.append("description missing")
    if not row.get("source_path"):
        reasons.append("path missing")
    elif not row.get("exists"):
        reasons.append("source file missing")
    elif not row.get("is_file"):
        reasons.append("source path is not a file")
    elif row.get("stat_error"):
        reasons.append(f"source file stat failed: {row['stat_error']}")
    if not reasons and source_path is not None:
        try:
            source_hash = _file_sha256(source_path)
        except OSError as exc:
            reasons.append(f"source file read failed: {exc}")
    if review_status not in REVIEWED_STATUSES:
        reasons.append("review_status PASS or FAIL missing")
    if review_status in REVIEWED_STATUSES and not rationale:
        reasons.append("review rationale missing")
    if reasons:
        return {
            **row,
            "status": "MISSING_EVIDENCE",
            "reason": "; ".join(reasons),
            "sha256": source_hash,
        }
    return {
        **row,
        "status": review_status,
        "reason": rationale,
        "sha256": source_hash,
    }


def _category_check(
    *,
    category: str,
    rows: Sequence[Mapping[str, Any]],
    inventory_path: Path,
) -> dict[str, Any]:
    reviewed_rows = [row for row in rows if row.get("status") in REVIEWED_STATUSES]
    if not reviewed_rows:
        reasons = sorted({str(row.get("reason")) for row in rows if row.get("reason")})
        reason = "; ".join(reasons) if reasons else f"{REQUIRED_CATEGORIES[category]} evidence is missing"
        return {
            "status": "MISSING_EVIDENCE",
            "reason": reason,
            "evidence_paths": [],
            "source_hashes": {},
            "source_inventory_path": _display_path(inventory_path),
        }
    statuses = {str(row.get("status")) for row in reviewed_rows}
    status = "FAIL" if "FAIL" in statuses else "PASS"
    if len(statuses) > 1:
        reason = "reviewed primary sources contain PASS and FAIL; FAIL is retained"
    else:
        reason = f"reviewed primary source evidence reported {status}"
    evidence_paths = [str(row["source_path"]) for row in reviewed_rows if row.get("source_path")]
    source_hashes = {
        str(row["source_path"]): str(row["sha256"])
        for row in reviewed_rows
        if row.get("source_path") and row.get("sha256")
    }
    source_sizes = {
        str(row["source_path"]): int(row["size_bytes"])
        for row in reviewed_rows
        if row.get("source_path") and row.get("size_bytes") is not None
    }
    return {
        "status": status,
        "reason": reason,
        "evidence_paths": evidence_paths,
        "source_hashes": source_hashes,
        "source_file_sizes": source_sizes,
        "source_inventory_path": _display_path(inventory_path),
        "reviewed_source_count": len(reviewed_rows),
    }


def build_payloads(
    *,
    run: str,
    prediction_path: Path,
    predictions_manifest: Path,
    source_manifest_path: Path,
    output_root: Path,
    max_source_files: int,
    max_total_bytes: int,
) -> dict[str, Mapping[str, Any]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    source_manifest = _read_json(source_manifest_path)
    raw_rows = _source_rows(source_manifest)
    source_manifest_display = _display_path(source_manifest_path)
    inventory_path = output_root / INVENTORY_NAME
    summary_path = output_root / SUMMARY_NAME
    readme_path = output_root / README_NAME
    base_rows = [
        _base_inventory_row(
            index=index,
            row=row,
            source_manifest_path=source_manifest_path,
        )
        for index, row in enumerate(raw_rows)
    ]
    total_source_bytes = sum(
        int(row["size_bytes"])
        for row in base_rows
        if row.get("exists") and row.get("is_file") and row.get("size_bytes") is not None
    )
    budget_failure = None
    if len(raw_rows) > max_source_files:
        budget_failure = (
            f"source file count {len(raw_rows)} exceeds max_source_files {max_source_files}"
        )
    elif total_source_bytes > max_total_bytes:
        budget_failure = (
            f"source byte count {total_source_bytes} exceeds max_total_bytes {max_total_bytes}"
        )
    inventory_rows = [
        _finalize_inventory_row(
            row,
            source_manifest_path=source_manifest_path,
            budget_failure=budget_failure,
        )
        for row in base_rows
    ]
    rows_by_category = {
        category: [row for row in inventory_rows if row.get("category") == category]
        for category in REQUIRED_CATEGORIES
    }
    check_results = {
        category: _category_check(
            category=category,
            rows=rows,
            inventory_path=inventory_path,
        )
        for category, rows in rows_by_category.items()
    }
    failures = [
        f"{REQUIRED_CATEGORIES[category]}: {check['reason']}"
        for category, check in check_results.items()
        if check["status"] != "PASS"
    ]
    status = "PASS" if not failures else "FAIL"
    inventory = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "run": run,
        "source_manifest_path": source_manifest_display,
        "source_manifest_sha256": _file_hash_or_missing(source_manifest_path),
        "max_source_files": max_source_files,
        "max_total_bytes": max_total_bytes,
        "source_file_count": len(raw_rows),
        "total_source_bytes": total_source_bytes,
        "budget_failure": budget_failure,
        "rows": inventory_rows,
    }
    summary = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "run": run,
        "prediction_path": _display_path(prediction_path),
        "predictions_manifest_path": _display_path(predictions_manifest),
        "source_manifest_path": source_manifest_display,
        "source_manifest_sha256": _file_hash_or_missing(source_manifest_path),
        "source_inventory_path": _display_path(inventory_path),
        "input_file_hashes": {
            _display_path(prediction_path): _file_hash_or_missing(prediction_path),
            _display_path(predictions_manifest): _file_hash_or_missing(predictions_manifest),
            source_manifest_display: _file_hash_or_missing(source_manifest_path),
        },
        "status": status,
        "execution_realism_gate": {
            "gate_name": "execution_realism_gate",
            "status": status,
            "execution_realism_ready": status == "PASS",
            "required_before_promotion": True,
            "required_checks": list(REQUIRED_CATEGORIES),
            "check_results": check_results,
            "failure_count": len(failures),
            "failures": failures,
            "policy": (
                "PASS/FAIL execution-realism rows require local primary source paths, "
                "computed source hashes, reviewed status, and review rationale"
            ),
        },
        "outputs": {
            "summary": _display_path(summary_path),
            "source_inventory": _display_path(inventory_path),
            "readme": _display_path(readme_path),
        },
    }
    return {"summary": summary, "inventory": inventory}


def build_markdown(summary: Mapping[str, Any]) -> str:
    gate = summary["execution_realism_gate"]
    lines = [
        "# Execution Realism Evidence Intake",
        "",
        f"- Run: `{summary['run']}`",
        f"- Status: `{gate['status']}`",
        f"- Source manifest: `{summary['source_manifest_path']}`",
        f"- Source inventory: `{summary['source_inventory_path']}`",
        "",
        "## Check Results",
        "",
    ]
    checks = gate["check_results"]
    for category in REQUIRED_CATEGORIES:
        check = checks[category]
        lines.append(
            f"- `{category}`: `{check['status']}` - {check['reason']}"
        )
    lines.extend(
        [
            "",
            "This report is an evidence intake artifact only. It does not run Phase 8, "
            "change the model, approve promotion, or approve paper/live trading.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    *,
    output_root: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    overwrite: bool,
) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / SUMMARY_NAME
    inventory_path = output_root / INVENTORY_NAME
    readme_path = output_root / README_NAME
    outputs = {
        "summary": summary_path,
        "source_inventory": inventory_path,
        "readme": readme_path,
    }
    if not overwrite:
        existing = [path for path in outputs.values() if path.exists()]
        if existing:
            raise FileExistsError(
                "refusing to overwrite existing execution-realism outputs: "
                + ", ".join(_display_path(path) for path in existing)
            )
    _write_json(summary_path, payloads["summary"])
    _write_json(inventory_path, payloads["inventory"])
    readme_path.write_text(build_markdown(payloads["summary"]), encoding="utf-8")
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--prediction-path", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-source-files", type=int, default=16)
    parser.add_argument("--max-total-bytes", type=int, default=268435456)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing intake outputs in the selected output root.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payloads = build_payloads(
        run=args.run,
        prediction_path=Path(args.prediction_path),
        predictions_manifest=Path(args.predictions_manifest),
        source_manifest_path=Path(args.source_manifest),
        output_root=Path(args.output_root),
        max_source_files=args.max_source_files,
        max_total_bytes=args.max_total_bytes,
    )
    outputs = write_outputs(
        output_root=Path(args.output_root),
        payloads=payloads,
        overwrite=args.overwrite,
    )
    gate = payloads["summary"]["execution_realism_gate"]
    print(
        gate["status"],
        "execution realism evidence intake:",
        f"failures={gate['failure_count']}",
        f"summary={_display_path(outputs['summary'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
