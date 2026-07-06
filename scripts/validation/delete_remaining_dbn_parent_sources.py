"""Delete already-promoted residual DBN parent-source evidence rows.

This is a narrow cleanup executor for the post row-archive state. It deletes
only the remaining KE statistics/status parent DBNs whose canonical targets
already hash-match, and leaves ohlcv_1m_parent untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_STATUS = "PASS_PARENT_SOURCE_DISPOSITION_READY_NO_EXECUTION"
TARGET_CLASSIFICATION = "already_promoted_or_excluded_from_parent_cleanup"
TARGET_ROOTS = {
    "data/dbn/statistics_parent",
    "data/dbn/status_parent",
}
FORBIDDEN_ROOTS = {
    "data/dbn/ohlcv_1m_parent",
    "data/dbn/sr1_sr3_2020_parent_sidecar_staging_20260705",
}
EXPECTED_DBN_ROWS = 8
EXPECTED_FILE_COUNT = 16
EXPECTED_MARKET_COUNTS = {"KE": 8}
EXPECTED_SCHEMA_COUNTS = {"statistics": 4, "status": 4}
EXPECTED_YEARS = {2019, 2021, 2023, 2024}
DEFAULT_SOURCE_JSON = (
    "reports/data_audit/current_state/dbn_parent_source_disposition_20260705.json"
)
DEFAULT_REPORT_JSON = (
    "reports/data_audit/current_state/"
    "dbn_remaining_parent_source_delete_20260705.json"
)
DEFAULT_REPORT_MD = (
    "reports/data_audit/current_state/"
    "dbn_remaining_parent_source_delete_20260705.md"
)


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def repo_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for_dbn(path: Path) -> Path:
    return path.with_name(path.name + ".manifest.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_safe_source_path(path_text: str) -> None:
    normalized = path_text.replace("\\", "/")
    if Path(normalized).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {path_text}")
    if ".." in Path(normalized).parts:
        raise ValueError(f"parent-directory path segments are not allowed: {path_text}")
    if not any(normalized.startswith(root + "/") for root in TARGET_ROOTS):
        raise ValueError(f"path is outside delete-approved roots: {path_text}")
    if any(normalized.startswith(root + "/") for root in FORBIDDEN_ROOTS):
        raise ValueError(f"forbidden root selected: {path_text}")


def load_target_rows(source_json: Path) -> list[dict[str, Any]]:
    payload = load_json(source_json)
    if not isinstance(payload, dict):
        raise ValueError(f"source JSON is not an object: {source_json}")
    if payload.get("status") != SOURCE_STATUS:
        raise ValueError(f"source status must be {SOURCE_STATUS}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("source rows are missing")
    target_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("classification") == TARGET_CLASSIFICATION
        and row.get("root") in TARGET_ROOTS
    ]
    if len(target_rows) != EXPECTED_DBN_ROWS:
        raise ValueError(f"expected {EXPECTED_DBN_ROWS} target DBN rows")
    return target_rows


def build_actions(repo_root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    keys: set[tuple[str, int, str]] = set()

    for index, row in enumerate(rows):
        market = str(row.get("market") or "")
        year = int(row.get("year") or 0)
        schema_key = str(row.get("schema_key") or "")
        key = (market, year, schema_key)
        if key in keys:
            raise ValueError(f"duplicate target row: {key}")
        keys.add(key)
        if market != "KE" or year not in EXPECTED_YEARS:
            raise ValueError(f"unexpected target market/year: {key}")
        if schema_key not in EXPECTED_SCHEMA_COUNTS:
            raise ValueError(f"unexpected target schema: {key}")

        source_text = str(row.get("path") or "").replace("\\", "/")
        manifest_text = str(row.get("manifest_path") or "").replace("\\", "/")
        canonical_text = str(row.get("canonical_target_path") or "").replace("\\", "/")
        require_safe_source_path(source_text)
        require_safe_source_path(manifest_text.removesuffix(".manifest.json"))
        source = repo_path(repo_root, source_text)
        manifest = repo_path(repo_root, manifest_text)
        canonical = repo_path(repo_root, canonical_text)
        source_sha = str(row.get("sha256") or "")
        manifest_sha = str(row.get("manifest_sha256") or "")
        canonical_sha = str(row.get("canonical_target_sha256") or "")

        if not source.is_file():
            raise ValueError(f"source DBN missing: {source_text}")
        if not manifest.is_file():
            raise ValueError(f"source manifest missing: {manifest_text}")
        if manifest != manifest_path_for_dbn(source):
            raise ValueError(f"manifest path mismatch for source: {source_text}")
        if not canonical.is_file():
            raise ValueError(f"canonical target missing: {canonical_text}")
        if row.get("canonical_target_matches_parent") is not True:
            raise ValueError(f"canonical target is not recorded as hash-matching: {key}")
        actual_source_sha = sha256_file(source)
        actual_manifest_sha = sha256_file(manifest)
        actual_canonical_sha = sha256_file(canonical)
        if actual_source_sha != source_sha:
            raise ValueError(f"source hash mismatch: {source_text}")
        if actual_manifest_sha != manifest_sha:
            raise ValueError(f"manifest hash mismatch: {manifest_text}")
        if actual_canonical_sha != canonical_sha:
            raise ValueError(f"canonical hash mismatch: {canonical_text}")
        if actual_source_sha != actual_canonical_sha:
            raise ValueError(f"source no longer matches canonical target: {source_text}")

        actions.append(
            {
                "market": market,
                "year": year,
                "schema_key": schema_key,
                "source": source_text,
                "source_sha256": actual_source_sha,
                "source_bytes": source.stat().st_size,
                "source_manifest": manifest_text,
                "source_manifest_sha256": actual_manifest_sha,
                "source_manifest_bytes": manifest.stat().st_size,
                "canonical_target": canonical_text,
                "canonical_target_sha256": actual_canonical_sha,
            }
        )

    verify_action_counts(actions)
    return actions


def verify_action_counts(actions: list[dict[str, Any]]) -> None:
    if len(actions) != EXPECTED_DBN_ROWS:
        raise ValueError("action row count mismatch")
    if len(actions) * 2 != EXPECTED_FILE_COUNT:
        raise ValueError("action file count mismatch")
    market_counts = dict(sorted(Counter(action["market"] for action in actions).items()))
    schema_counts = dict(sorted(Counter(action["schema_key"] for action in actions).items()))
    if market_counts != EXPECTED_MARKET_COUNTS:
        raise ValueError(f"unexpected market counts: {market_counts}")
    if schema_counts != EXPECTED_SCHEMA_COUNTS:
        raise ValueError(f"unexpected schema counts: {schema_counts}")


def delete_actions(repo_root: Path, actions: list[dict[str, Any]]) -> None:
    for action in actions:
        source = repo_path(repo_root, action["source"])
        manifest = repo_path(repo_root, action["source_manifest"])
        if not source.is_file() or not manifest.is_file():
            raise ValueError(f"source pair disappeared before delete: {action['source']}")
        source.unlink()
        manifest.unlink()
        if source.exists() or manifest.exists():
            raise ValueError(f"source pair still exists after delete: {action['source']}")
    remove_empty_target_dirs(repo_root)


def remove_empty_target_dirs(repo_root: Path) -> list[str]:
    removed: list[str] = []
    for root_text in sorted(TARGET_ROOTS):
        root = repo_path(repo_root, root_text)
        if not root.exists():
            continue
        for directory in sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
                removed.append(rel(directory, repo_root))
            except OSError:
                pass
        try:
            root.rmdir()
            removed.append(rel(root, repo_root))
        except OSError:
            pass
    return removed


def verify_forbidden_preserved(repo_root: Path) -> dict[str, Any]:
    ohlcv_root = repo_path(repo_root, "data/dbn/ohlcv_1m_parent")
    sr_paths = [
        ohlcv_root / "SR1/2020/2020-01-01_2021-01-01.dbn.zst",
        ohlcv_root / "SR3/2020/2020-01-01_2021-01-01.dbn.zst",
    ]
    sidecar_root = repo_path(
        repo_root, "data/dbn/sr1_sr3_2020_parent_sidecar_staging_20260705"
    )
    sidecar_files = (
        sorted(path for path in sidecar_root.rglob("*") if path.is_file())
        if sidecar_root.exists()
        else []
    )
    ohlcv_files = sorted(path for path in ohlcv_root.rglob("*") if path.is_file())
    return {
        "ohlcv_1m_parent_exists": ohlcv_root.is_dir(),
        "ohlcv_1m_parent_file_count": len(ohlcv_files),
        "protected_sr_ohlcv_sources": [
            {"path": rel(path, repo_root), "exists": path.is_file()} for path in sr_paths
        ],
        "protected_sidecar_root_exists": sidecar_root.is_dir(),
        "protected_sidecar_file_count": len(sidecar_files),
    }


def build_report(
    repo_root: Path,
    source_json: Path,
    report_json: Path,
    report_md: Path,
    execute: bool,
) -> dict[str, Any]:
    rows = load_target_rows(source_json)
    actions = build_actions(repo_root, rows)
    removed_empty_dirs: list[str] = []
    if execute:
        delete_actions(repo_root, actions)
        removed_empty_dirs = remove_empty_target_dirs(repo_root)
    report = {
        "stage": "dbn_remaining_parent_source_delete",
        "status": "DELETED" if execute else "DRY_RUN_READY",
        "executed": execute,
        "generated_at_utc": utc_now(),
        "source_json": rel(source_json, repo_root),
        "report_json": rel(report_json, repo_root),
        "report_md": rel(report_md, repo_root),
        "bounds": {
            "target_roots": sorted(TARGET_ROOTS),
            "forbidden_roots": sorted(FORBIDDEN_ROOTS),
            "expected_dbn_rows": EXPECTED_DBN_ROWS,
            "expected_file_count_including_manifests": EXPECTED_FILE_COUNT,
            "deletes_only_already_promoted_ke_statistics_status_rows": True,
        },
        "summary": {
            "dbn_row_count": len(actions),
            "file_count_including_manifests": len(actions) * 2,
            "market_counts": dict(
                sorted(Counter(action["market"] for action in actions).items())
            ),
            "schema_counts": dict(
                sorted(Counter(action["schema_key"] for action in actions).items())
            ),
            "year_counts": dict(
                sorted(Counter(str(action["year"]) for action in actions).items())
            ),
        },
        "forbidden_preservation": verify_forbidden_preserved(repo_root),
        "removed_empty_directories": removed_empty_dirs,
        "actions": actions,
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    if summary["dbn_row_count"] != EXPECTED_DBN_ROWS:
        raise ValueError("report DBN row count mismatch")
    if summary["file_count_including_manifests"] != EXPECTED_FILE_COUNT:
        raise ValueError("report file count mismatch")
    if summary["market_counts"] != EXPECTED_MARKET_COUNTS:
        raise ValueError("report market count mismatch")
    if summary["schema_counts"] != EXPECTED_SCHEMA_COUNTS:
        raise ValueError("report schema count mismatch")
    preserved = report["forbidden_preservation"]
    if not preserved["ohlcv_1m_parent_exists"]:
        raise ValueError("ohlcv_1m_parent was not preserved")
    if preserved["ohlcv_1m_parent_file_count"] != 12:
        raise ValueError("ohlcv_1m_parent file count changed")
    if not all(row["exists"] for row in preserved["protected_sr_ohlcv_sources"]):
        raise ValueError("protected SR OHLCV source missing")
    if not preserved["protected_sidecar_root_exists"]:
        raise ValueError("protected SR sidecar root missing")
    if preserved["protected_sidecar_file_count"] != 8:
        raise ValueError("protected SR sidecar file count changed")


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Remaining DBN Parent-Source Delete",
        "",
        f"- Status: `{report['status']}`.",
        f"- Executed: `{report['executed']}`.",
        f"- Source JSON: `{report['source_json']}`.",
        "",
        "## Scope",
        "",
        f"- DBN rows: `{report['summary']['dbn_row_count']}`.",
        f"- Files including manifests: `{report['summary']['file_count_including_manifests']}`.",
        f"- Market counts: `{json.dumps(report['summary']['market_counts'], sort_keys=True)}`.",
        f"- Schema counts: `{json.dumps(report['summary']['schema_counts'], sort_keys=True)}`.",
        f"- Year counts: `{json.dumps(report['summary']['year_counts'], sort_keys=True)}`.",
        "",
        "## Preserved",
        "",
        f"- `data/dbn/ohlcv_1m_parent` exists: `{report['forbidden_preservation']['ohlcv_1m_parent_exists']}`.",
        f"- `data/dbn/ohlcv_1m_parent` file count: `{report['forbidden_preservation']['ohlcv_1m_parent_file_count']}`.",
        f"- SR sidecar root exists: `{report['forbidden_preservation']['protected_sidecar_root_exists']}`.",
        f"- SR sidecar file count: `{report['forbidden_preservation']['protected_sidecar_file_count']}`.",
        "",
        "## Deleted Rows",
        "",
        "| Market | Year | Schema | Source | Canonical target |",
        "|---|---:|---|---|---|",
    ]
    for action in report["actions"]:
        lines.append(
            "| `{market}` | `{year}` | `{schema_key}` | `{source}` | `{canonical_target}` |".format(
                **action
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--report-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    source_json = repo_path(repo_root, args.source_json)
    report_json = repo_path(repo_root, args.report_json)
    report_md = repo_path(repo_root, args.report_md)
    report = build_report(repo_root, source_json, report_json, report_md, args.execute)
    write_json(report_json, report)
    write_markdown(report, report_md)
    print(
        json.dumps(
            {
                "status": report["status"],
                "executed": report["executed"],
                "summary": report["summary"],
                "report_json": report["report_json"],
                "report_md": report["report_md"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
