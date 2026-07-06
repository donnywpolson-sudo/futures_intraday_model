"""Approval-gated HE/KE/LE DBN parent-source consolidation helper.

This module intentionally separates decision packets, staging, promotion, raw
lineage validation, and parent-root archiving. Mutating modes are dry-run by
default and require --execute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MARKETS = {"HE", "KE", "LE"}
SCHEMAS = {"ohlcv_1m", "statistics", "status"}
APPROVED_ACTION = "promote_parent"
ARCHIVE_DISPOSITIONS = {
    "promoted_parent",
    "kept_canonical_archive_parent_candidate",
    "blocked",
}
DEFAULT_AUDIT_JSON = Path("reports/data_audit/he_ke_le_dbn_parent_source_audit.json")
DEFAULT_DECISIONS_JSON = Path(
    "reports/data_audit/he_ke_le_dbn_parent_consolidation_decisions.json"
)
DEFAULT_DECISIONS_MD = Path(
    "reports/data_audit/he_ke_le_dbn_parent_consolidation_decisions.md"
)


PARENT_TO_CANONICAL_PREFIXES = {
    "data/dbn/ohlcv_1m_parent/": "data/dbn/ohlcv_1m/",
    "data/dbn/statistics_parent/statistics/": "data/dbn/statistics/",
    "data/dbn/status_parent/status/": "data/dbn/status/",
}


PARENT_ROOTS = [
    Path("data/dbn/ohlcv_1m_parent"),
    Path("data/dbn/statistics_parent"),
    Path("data/dbn/status_parent"),
]


@dataclass(frozen=True)
class ApprovalRow:
    market: str
    year: int
    schema_key: str
    parent_path: str
    parent_sha256: str
    canonical_target_path: str
    approved_action: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel_posix(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def repo_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_target_for_parent(parent_path: str) -> str:
    normalized = parent_path.replace("\\", "/")
    for parent_prefix, canonical_prefix in PARENT_TO_CANONICAL_PREFIXES.items():
        if normalized.startswith(parent_prefix):
            return canonical_prefix + normalized.removeprefix(parent_prefix)
    raise ValueError(f"parent_path is outside supported parent roots: {parent_path}")


def manifest_path_for_dbn(dbn_path: Path) -> Path:
    return dbn_path.with_name(dbn_path.name + ".manifest.json")


def load_audit(path: Path) -> Mapping[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"audit JSON is not an object: {path}")
    summary = payload.get("summary")
    if not isinstance(summary, dict) or summary.get("validation_status") != "PASS":
        raise ValueError("parent-source audit must have summary.validation_status == PASS")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("parent-source audit rows are missing")
    return payload


def _single_parent_candidate(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    candidates = row.get("parent_manifest_source_summary")
    if not isinstance(candidates, list) or len(candidates) != 1:
        return None
    candidate = candidates[0]
    return candidate if isinstance(candidate, Mapping) else None


def decision_for_audit_row(row: Mapping[str, Any]) -> dict[str, Any]:
    market = str(row.get("market") or "")
    year = int(row.get("year") or 0)
    schema_key = str(row.get("schema_key") or "")
    if market not in MARKETS or schema_key not in SCHEMAS:
        raise ValueError(f"out-of-scope audit row: {market} {year} {schema_key}")

    parent_candidate = _single_parent_candidate(row)
    parent_path = str(parent_candidate.get("path") or "") if parent_candidate else ""
    parent_sha256 = str(parent_candidate.get("file_sha256") or "") if parent_candidate else ""
    canonical_target = canonical_target_for_parent(parent_path) if parent_path else ""

    classification = str(row.get("classification") or "")
    if not parent_path:
        recommendation = "keep_canonical"
        reason = "no parent candidate in audit row"
    elif classification == "parquet_uses_parent":
        recommendation = APPROVED_ACTION
        reason = "current raw parquet lineage already references parent source"
    elif bool(row.get("parent_exists_and_differs_from_canonical")):
        recommendation = "review_required"
        reason = "parent and canonical both exist and differ"
    else:
        recommendation = "keep_canonical"
        reason = "parent candidate is not current lineage and no replacement is approved"

    return {
        "market": market,
        "year": year,
        "schema_key": schema_key,
        "classification": classification,
        "recommendation": recommendation,
        "reason": reason,
        "parent_path": parent_path,
        "parent_sha256": parent_sha256,
        "canonical_target_path": canonical_target,
        "parent_newer_than_canonical": row.get("parent_newer_than_canonical"),
        "parent_exists_and_differs_from_canonical": row.get(
            "parent_exists_and_differs_from_canonical"
        ),
        "approval_template": (
            {
                "market": market,
                "year": year,
                "schema_key": schema_key,
                "parent_path": parent_path,
                "parent_sha256": parent_sha256,
                "canonical_target_path": canonical_target,
                "approved_action": APPROVED_ACTION,
            }
            if recommendation == APPROVED_ACTION
            else None
        ),
    }


def build_decision_packet(audit: Mapping[str, Any]) -> dict[str, Any]:
    audit_rows = audit["rows"]
    decisions = [decision_for_audit_row(row) for row in audit_rows]
    counts = Counter(str(row["recommendation"]) for row in decisions)
    approved_candidates = [
        row["approval_template"] for row in decisions if row.get("approval_template")
    ]
    return {
        "generated_at_utc": utc_now(),
        "source_audit": str(DEFAULT_AUDIT_JSON).replace("\\", "/"),
        "scope": {
            "markets": sorted(MARKETS),
            "schemas": sorted(SCHEMAS),
            "promotion_policy": "approval_gated_per_row",
        },
        "summary": {
            "decision_count": len(decisions),
            "recommendation_counts": dict(sorted(counts.items())),
            "approval_template_count": len(approved_candidates),
            "default_parent_lineage_market_years": sorted(
                {
                    f"{row['market']}:{row['year']}"
                    for row in decisions
                    if row["recommendation"] == APPROVED_ACTION
                }
            ),
        },
        "approval_file_contract": {
            "top_level_key": "approvals",
            "required_fields": [
                "market",
                "year",
                "schema_key",
                "parent_path",
                "parent_sha256",
                "canonical_target_path",
                "approved_action",
            ],
            "only_promoted_action": APPROVED_ACTION,
            "wildcards_allowed": False,
        },
        "approval_template": {"approvals": approved_candidates},
        "decisions": decisions,
    }


def write_decision_markdown(path: Path, packet: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    decisions = list(packet["decisions"])
    counts = packet["summary"]["recommendation_counts"]
    parent_rows = [
        row for row in decisions if row["recommendation"] == APPROVED_ACTION
    ]
    review_rows = [row for row in decisions if row["recommendation"] == "review_required"]
    lines = [
        "# HE/KE/LE DBN Parent Consolidation Decisions",
        "",
        f"Generated: `{packet['generated_at_utc']}`",
        "",
        "## Summary",
        "",
        f"- Decision rows: `{packet['summary']['decision_count']}`.",
        f"- Recommendation counts: `{json.dumps(counts, sort_keys=True)}`.",
        "- Promotion policy: approval-gated per row; no wildcard promotion.",
        "",
        "## Default Promote Candidates",
        "",
    ]
    if parent_rows:
        lines.extend(
            [
                "| Market | Year | Schema | Parent path | Canonical target |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in parent_rows:
            lines.append(
                "| {market} | {year} | {schema_key} | `{parent_path}` | `{canonical_target_path}` |".format(
                    **row
                )
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Review Required", ""])
    if review_rows:
        lines.extend(
            [
                "| Market | Year | Schema | Reason | Parent path |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in review_rows:
            lines.append(
                "| {market} | {year} | {schema_key} | {reason} | `{parent_path}` |".format(
                    **row
                )
            )
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Approval Contract",
            "",
            "Use the JSON `approval_template.approvals` rows as the starting point. "
            "Rows marked `review_required` must be explicitly edited to "
            "`approved_action: promote_parent` before staging.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_approval_rows(path: Path) -> list[ApprovalRow]:
    payload = read_json(path)
    rows = payload.get("approvals") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("approval JSON must be an object with an approvals list")
    approvals: list[ApprovalRow] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"approval row {index} is not an object")
        required = {
            "market",
            "year",
            "schema_key",
            "parent_path",
            "parent_sha256",
            "canonical_target_path",
            "approved_action",
        }
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(f"approval row {index} missing fields: {', '.join(missing)}")
        approval = ApprovalRow(
            market=str(row["market"]),
            year=int(row["year"]),
            schema_key=str(row["schema_key"]),
            parent_path=str(row["parent_path"]).replace("\\", "/"),
            parent_sha256=str(row["parent_sha256"]),
            canonical_target_path=str(row["canonical_target_path"]).replace("\\", "/"),
            approved_action=str(row["approved_action"]),
        )
        validate_approval_shape(approval, index)
        approvals.append(approval)
    if len({(row.market, row.year, row.schema_key) for row in approvals}) != len(approvals):
        raise ValueError("approval JSON contains duplicate market/year/schema rows")
    return approvals


def validate_approval_shape(row: ApprovalRow, index: int = 0) -> None:
    if row.market not in MARKETS:
        raise ValueError(f"approval row {index} market out of scope: {row.market}")
    if row.schema_key not in SCHEMAS:
        raise ValueError(f"approval row {index} schema_key out of scope: {row.schema_key}")
    if row.approved_action != APPROVED_ACTION:
        raise ValueError(
            f"approval row {index} approved_action must be {APPROVED_ACTION!r}"
        )
    if any("*" in value for value in (row.parent_path, row.canonical_target_path)):
        raise ValueError(f"approval row {index} contains wildcard paths")
    expected_target = canonical_target_for_parent(row.parent_path)
    if row.canonical_target_path != expected_target:
        raise ValueError(
            f"approval row {index} canonical_target_path {row.canonical_target_path!r} "
            f"does not match expected {expected_target!r}"
        )


def audit_lookup(audit: Mapping[str, Any]) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    return {
        (str(row["market"]), int(row["year"]), str(row["schema_key"])): row
        for row in audit["rows"]
        if isinstance(row, Mapping)
    }


def validate_approvals_against_audit(
    approvals: Sequence[ApprovalRow], audit: Mapping[str, Any], repo_root: Path
) -> None:
    rows = audit_lookup(audit)
    for approval in approvals:
        key = (approval.market, approval.year, approval.schema_key)
        audit_row = rows.get(key)
        if not audit_row:
            raise ValueError(f"approval row not present in audit: {key}")
        parent_path = repo_path(repo_root, approval.parent_path)
        if not parent_path.is_file():
            raise ValueError(f"approved parent file missing: {approval.parent_path}")
        actual_sha = sha256_file(parent_path)
        if actual_sha != approval.parent_sha256:
            raise ValueError(
                f"approved parent hash mismatch for {approval.parent_path}: "
                f"expected {approval.parent_sha256}, actual {actual_sha}"
            )
        candidate = _single_parent_candidate(audit_row)
        if not candidate or str(candidate.get("path") or "") != approval.parent_path:
            raise ValueError(f"approval parent path does not match audit row: {key}")
        if str(candidate.get("file_sha256") or "") != approval.parent_sha256:
            raise ValueError(f"approval parent hash does not match audit row: {key}")


def git_status_for_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    args = ["git", "status", "--short", "--", *sorted(set(paths))]
    result = subprocess.run(
        args,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def preflight_no_tracked_target_changes(repo_root: Path, approvals: Sequence[ApprovalRow]) -> None:
    status_lines = git_status_for_paths(
        repo_root, [row.canonical_target_path for row in approvals]
    )
    if status_lines:
        raise ValueError(
            "approved target paths have tracked git status; refusing promotion preflight: "
            + "; ".join(status_lines)
        )


def copy_manifest_with_canonical_path(
    source_manifest: Path, target_manifest: Path, canonical_target_path: str
) -> None:
    payload = read_json(source_manifest)
    if not isinstance(payload, dict):
        raise ValueError(f"manifest is not an object: {source_manifest}")
    payload["path"] = canonical_target_path
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    target_manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stage_approved(
    repo_root: Path,
    approvals: Sequence[ApprovalRow],
    *,
    staging_root: Path,
    timestamp: str,
    execute: bool,
) -> dict[str, Any]:
    run_root = repo_path(repo_root, staging_root) / timestamp / "canonical_layout"
    actions = []
    for approval in approvals:
        parent_path = repo_path(repo_root, approval.parent_path)
        parent_manifest = manifest_path_for_dbn(parent_path)
        if not parent_manifest.is_file():
            raise ValueError(f"approved parent manifest missing: {rel_posix(parent_manifest, repo_root)}")
        target_path = run_root / approval.canonical_target_path
        target_manifest = manifest_path_for_dbn(target_path)
        actions.append(
            {
                "action": "copy_parent_to_staging",
                "source": approval.parent_path,
                "source_manifest": rel_posix(parent_manifest, repo_root),
                "target": rel_posix(target_path, repo_root),
                "target_manifest": rel_posix(target_manifest, repo_root),
                "manifest_path_rewrite": approval.canonical_target_path,
            }
        )
        if execute:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(parent_path, target_path)
            copy_manifest_with_canonical_path(
                parent_manifest, target_manifest, approval.canonical_target_path
            )
            staged_hash = sha256_file(target_path)
            if staged_hash != approval.parent_sha256:
                raise ValueError(f"staged hash mismatch: {rel_posix(target_path, repo_root)}")
    return {
        "generated_at_utc": utc_now(),
        "mode": "stage-approved",
        "executed": execute,
        "staging_run_root": rel_posix(run_root, repo_root),
        "approved_row_count": len(approvals),
        "actions": actions,
        "raw_regeneration_commands": raw_regeneration_commands(approvals, "data/raw_parent_consolidation_staging"),
    }


def raw_regeneration_commands(
    approvals: Sequence[ApprovalRow], staged_raw_root: str
) -> list[dict[str, Any]]:
    market_years = sorted({(row.market, row.year) for row in approvals})
    commands = []
    for market, year in market_years:
        end_year = year + 1
        command = (
            "python -m scripts.phase1A_download.download_databento_raw "
            f"--mode convert-parquet --symbols {market} --start {year}-01-01 "
            f"--end {end_year}-01-01 --dbn-root data/dbn/ohlcv_1m "
            f"--raw-root {staged_raw_root} --include-optional-schemas status,statistics "
            "--optional-dbn-root data/dbn --offline-local-conditions"
        )
        commands.append(
            {
                "market": market,
                "year": year,
                "command": command,
                "expected_staged_raw": f"{staged_raw_root}/{market}/{year}.parquet",
            }
        )
    return commands


def promote_approved(
    repo_root: Path,
    approvals: Sequence[ApprovalRow],
    *,
    staging_run_root: Path,
    archive_root: Path,
    timestamp: str,
    execute: bool,
) -> dict[str, Any]:
    staging_root = repo_path(repo_root, staging_run_root)
    archive_base = repo_path(repo_root, archive_root) / timestamp
    actions = []
    for approval in approvals:
        target = repo_path(repo_root, approval.canonical_target_path)
        staged = staging_root / approval.canonical_target_path
        staged_manifest = manifest_path_for_dbn(staged)
        if not staged.is_file() or not staged_manifest.is_file():
            raise ValueError(f"staged DBN/manifest missing for {approval.canonical_target_path}")
        if sha256_file(staged) != approval.parent_sha256:
            raise ValueError(f"staged hash mismatch for {rel_posix(staged, repo_root)}")

        archive_target = archive_base / approval.canonical_target_path
        archive_manifest = manifest_path_for_dbn(archive_target)
        target_manifest = manifest_path_for_dbn(target)
        if target.exists() and not target_manifest.exists():
            raise ValueError(f"canonical DBN exists without manifest: {approval.canonical_target_path}")
        if target.exists() and archive_target.exists():
            raise ValueError(f"archive target already exists: {rel_posix(archive_target, repo_root)}")
        actions.append(
            {
                "action": "archive_then_promote",
                "target": approval.canonical_target_path,
                "staged": rel_posix(staged, repo_root),
                "archive": rel_posix(archive_target, repo_root) if target.exists() else None,
            }
        )
        if execute:
            if target.exists():
                archive_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, archive_target)
                shutil.copy2(target_manifest, archive_manifest)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, target)
            shutil.copy2(staged_manifest, target_manifest)
            manifest = read_json(target_manifest)
            if not isinstance(manifest, dict) or manifest.get("path") != approval.canonical_target_path:
                raise ValueError(f"promoted manifest path mismatch: {approval.canonical_target_path}")
    return {
        "generated_at_utc": utc_now(),
        "mode": "promote-approved",
        "executed": execute,
        "archive_root": rel_posix(archive_base, repo_root),
        "approved_row_count": len(approvals),
        "actions": actions,
        "raw_regeneration_commands": raw_regeneration_commands(approvals, "data/raw_parent_consolidation_staging"),
    }


def validate_manifest_hash_and_path(path: Path, repo_root: Path) -> list[str]:
    failures = []
    manifest_path = manifest_path_for_dbn(path)
    if not manifest_path.is_file():
        return [f"manifest missing: {rel_posix(manifest_path, repo_root)}"]
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        return [f"manifest invalid: {rel_posix(manifest_path, repo_root)}"]
    actual = sha256_file(path)
    if manifest.get("file_sha256") != actual:
        failures.append(f"manifest hash mismatch: {rel_posix(path, repo_root)}")
    if manifest.get("path") != rel_posix(path, repo_root):
        failures.append(f"manifest path mismatch: {rel_posix(manifest_path, repo_root)}")
    return failures


def validate_promoted_targets(repo_root: Path, approvals: Sequence[ApprovalRow]) -> dict[str, Any]:
    failures: list[str] = []
    for approval in approvals:
        target = repo_path(repo_root, approval.canonical_target_path)
        if not target.is_file():
            failures.append(f"promoted target missing: {approval.canonical_target_path}")
            continue
        actual = sha256_file(target)
        if actual != approval.parent_sha256:
            failures.append(f"promoted target hash mismatch: {approval.canonical_target_path}")
        failures.extend(validate_manifest_hash_and_path(target, repo_root))
    raw_failures = validate_raw_lineage(repo_root, approvals)
    failures.extend(raw_failures)
    return {
        "generated_at_utc": utc_now(),
        "mode": "validate",
        "status": "PASS" if not failures else "FAIL",
        "approved_row_count": len(approvals),
        "failures": failures,
    }


def validate_raw_lineage(repo_root: Path, approvals: Sequence[ApprovalRow]) -> list[str]:
    try:
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - pyarrow is available in repo env.
        return [f"pyarrow unavailable for raw parquet validation: {exc}"]

    by_market_year: dict[tuple[str, int], list[ApprovalRow]] = {}
    for approval in approvals:
        by_market_year.setdefault((approval.market, approval.year), []).append(approval)

    failures: list[str] = []
    for (market, year), rows in sorted(by_market_year.items()):
        raw_path = repo_root / "data" / "raw" / market / f"{year}.parquet"
        if not raw_path.is_file():
            failures.append(f"raw parquet missing: {rel_posix(raw_path, repo_root)}")
            continue
        parquet = pq.ParquetFile(raw_path)
        columns = set(parquet.schema.names)
        needed = {"source_file", "source_sha256", "status_source_file", "status_source_sha256"}
        stat_source_columns = {col for col in columns if col.startswith("stat_") and col.endswith("_source_file")}
        needed.update(stat_source_columns)
        needed.update(col.removesuffix("_source_file") + "_source_sha256" for col in stat_source_columns)
        read_cols = sorted(col for col in needed if col in columns)
        if not read_cols:
            failures.append(f"raw parquet lineage columns missing: {rel_posix(raw_path, repo_root)}")
            continue
        table = pq.read_table(raw_path, columns=read_cols)
        values_by_col = {
            name: {str(value) for value in table.column(name).drop_null().unique().to_pylist()}
            for name in read_cols
        }
        for approval in rows:
            if approval.schema_key == "ohlcv_1m":
                source_cols = ["source_file"]
            elif approval.schema_key == "status":
                source_cols = ["status_source_file"]
            else:
                source_cols = sorted(stat_source_columns)
            populated_statistics_source = False
            for source_col in source_cols:
                values = {value.replace("\\", "/") for value in values_by_col.get(source_col, set())}
                if any("_parent" in value for value in values):
                    failures.append(
                        f"raw parquet still references parent in {source_col}: {rel_posix(raw_path, repo_root)}"
                    )
                if approval.schema_key == "statistics" and not values:
                    continue
                if approval.schema_key == "statistics":
                    populated_statistics_source = True
                if approval.canonical_target_path not in values:
                    failures.append(
                        f"raw parquet missing canonical source {approval.canonical_target_path} "
                        f"in {source_col}: {rel_posix(raw_path, repo_root)}"
                    )
            if approval.schema_key == "statistics" and not populated_statistics_source:
                failures.append(
                    f"raw parquet missing populated statistics lineage: {rel_posix(raw_path, repo_root)}"
                )
    return failures


def parse_disposition_rows(path: Path) -> dict[str, str]:
    payload = read_json(path)
    rows = payload.get("dispositions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("disposition JSON must be an object with a dispositions list")
    dispositions: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"disposition row {index} is not an object")
        parent_path = str(row.get("parent_path") or "").replace("\\", "/")
        disposition = str(row.get("disposition") or "")
        if not parent_path:
            raise ValueError(f"disposition row {index} missing parent_path")
        if disposition not in ARCHIVE_DISPOSITIONS:
            raise ValueError(f"disposition row {index} has invalid disposition: {disposition}")
        dispositions[parent_path] = disposition
    return dispositions


def archive_parent_roots(
    repo_root: Path,
    dispositions: Mapping[str, str],
    *,
    archive_root: Path,
    timestamp: str,
    execute: bool,
) -> dict[str, Any]:
    parent_files = sorted(
        rel_posix(path, repo_root)
        for root in PARENT_ROOTS
        for path in (repo_root / root).glob("**/*.dbn.zst")
    )
    missing = [path for path in parent_files if path not in dispositions]
    blocked = [path for path, disposition in dispositions.items() if disposition == "blocked"]
    if missing or blocked:
        return {
            "generated_at_utc": utc_now(),
            "mode": "archive-parent-roots",
            "executed": False,
            "status": "BLOCKED",
            "missing_disposition_count": len(missing),
            "blocked_count": len(blocked),
            "missing_dispositions": missing[:50],
            "blocked": blocked[:50],
        }
    archive_base = repo_path(repo_root, archive_root) / timestamp
    actions = []
    for root in PARENT_ROOTS:
        source = repo_root / root
        target = archive_base / root.name
        actions.append(
            {
                "action": "archive_parent_root",
                "source": rel_posix(source, repo_root),
                "target": rel_posix(target, repo_root),
            }
        )
        if execute and source.exists():
            if target.exists():
                raise ValueError(f"archive parent root target already exists: {rel_posix(target, repo_root)}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    return {
        "generated_at_utc": utc_now(),
        "mode": "archive-parent-roots",
        "executed": execute,
        "status": "READY" if not execute else "ARCHIVED",
        "parent_file_count": len(parent_files),
        "actions": actions,
    }


def write_report(report_out: Path | None, payload: Mapping[str, Any]) -> None:
    if report_out:
        write_json(report_out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "decision-packet",
            "stage-approved",
            "promote-approved",
            "validate",
            "archive-parent-roots",
        ],
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--audit-json", default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument("--approval-json")
    parser.add_argument("--disposition-json")
    parser.add_argument("--decisions-json", default=str(DEFAULT_DECISIONS_JSON))
    parser.add_argument("--decisions-md", default=str(DEFAULT_DECISIONS_MD))
    parser.add_argument("--staging-root", default="data/dbn/_promotion_staging")
    parser.add_argument("--staging-run-root")
    parser.add_argument("--archive-root", default="data/dbn/_archive_parent_consolidation")
    parser.add_argument("--parent-archive-root", default="data/dbn/_archive_parent_roots")
    parser.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--report-out")
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    audit_path = repo_path(repo_root, args.audit_json)
    report_out = repo_path(repo_root, args.report_out) if args.report_out else None

    if args.mode == "decision-packet":
        audit = load_audit(audit_path)
        packet = build_decision_packet(audit)
        decisions_json = repo_path(repo_root, args.decisions_json)
        decisions_md = repo_path(repo_root, args.decisions_md)
        write_json(decisions_json, packet)
        write_decision_markdown(decisions_md, packet)
        payload = {
            "mode": args.mode,
            "status": "WROTE_DECISION_PACKET",
            "decisions_json": rel_posix(decisions_json, repo_root),
            "decisions_md": rel_posix(decisions_md, repo_root),
            "summary": packet["summary"],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.mode in {"stage-approved", "promote-approved", "validate"}:
        if not args.approval_json:
            raise SystemExit("--approval-json is required")
        audit = load_audit(audit_path)
        approvals = parse_approval_rows(repo_path(repo_root, args.approval_json))
        validate_approvals_against_audit(approvals, audit, repo_root)
        if args.mode in {"stage-approved", "promote-approved"}:
            preflight_no_tracked_target_changes(repo_root, approvals)
        if args.mode == "stage-approved":
            payload = stage_approved(
                repo_root,
                approvals,
                staging_root=Path(args.staging_root),
                timestamp=args.timestamp,
                execute=args.execute,
            )
        elif args.mode == "promote-approved":
            if not args.staging_run_root:
                raise SystemExit("--staging-run-root is required")
            payload = promote_approved(
                repo_root,
                approvals,
                staging_run_root=Path(args.staging_run_root),
                archive_root=Path(args.archive_root),
                timestamp=args.timestamp,
                execute=args.execute,
            )
        else:
            payload = validate_promoted_targets(repo_root, approvals)
        write_report(report_out, payload)
        return 0 if payload.get("status") != "FAIL" else 1

    if args.mode == "archive-parent-roots":
        if not args.disposition_json:
            raise SystemExit("--disposition-json is required")
        dispositions = parse_disposition_rows(repo_path(repo_root, args.disposition_json))
        payload = archive_parent_roots(
            repo_root,
            dispositions,
            archive_root=Path(args.parent_archive_root),
            timestamp=args.timestamp,
            execute=args.execute,
        )
        write_report(report_out, payload)
        return 0 if payload["status"] != "BLOCKED" else 1

    raise SystemExit(f"unsupported mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main())
