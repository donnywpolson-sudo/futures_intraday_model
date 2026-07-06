"""Move approved DBN parent-source archive-candidate rows out of data/dbn.

This executor is intentionally narrower than whole-root parent archiving. It
uses the canonical-policy report as an exact allow-list and refuses to move any
row outside the 112 archive-candidate DBN rows named by that report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_STATUS = "PASS_DBN_PARENT_SOURCE_CANONICAL_POLICY_READY_NO_EXECUTION"
EXPECTED_DBN_ROWS = 112
EXPECTED_FILE_COUNT = 224
ARCHIVE_DECISIONS = {
    "archive_candidate_canonical_phase2_lineage",
    "archive_candidate_after_status_decoded_equality_proof",
}
EXPECTED_DECISION_COUNTS = {
    "archive_candidate_canonical_phase2_lineage": 106,
    "archive_candidate_after_status_decoded_equality_proof": 6,
}
PROTECTED_PATH_FRAGMENTS = {
    "sr1_sr3_2020_parent_sidecar_staging_20260705",
}
PROTECTED_ROW_KEYS = {
    ("SR1", 2020, "ohlcv_1m"),
    ("SR3", 2020, "ohlcv_1m"),
}
DEFAULT_POLICY_JSON = (
    "reports/data_audit/current_state/"
    "dbn_parent_source_canonical_policy_20260705.json"
)
DEFAULT_ARCHIVE_ROOT = "archive/dbn_parent_source_row_archive_20260705"
DEFAULT_REPORT_JSON = (
    "reports/data_audit/current_state/"
    "dbn_parent_source_row_archive_20260705.json"
)
DEFAULT_REPORT_MD = (
    "reports/data_audit/current_state/"
    "dbn_parent_source_row_archive_20260705.md"
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


def dbn_manifest_path(dbn_path: Path) -> Path:
    return dbn_path.with_name(dbn_path.name + ".manifest.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_safe_relative_path(path_text: str) -> None:
    normalized = path_text.replace("\\", "/")
    if Path(normalized).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {path_text}")
    if ".." in Path(normalized).parts:
        raise ValueError(f"parent-directory path segments are not allowed: {path_text}")
    if not normalized.startswith(
        (
            "data/dbn/ohlcv_1m_parent/",
            "data/dbn/statistics_parent/",
            "data/dbn/status_parent/",
        )
    ):
        raise ValueError(f"parent row is outside approved parent roots: {path_text}")
    if any(fragment in normalized for fragment in PROTECTED_PATH_FRAGMENTS):
        raise ValueError(f"protected path fragment selected: {path_text}")


def load_policy_rows(policy_json: Path) -> list[dict[str, Any]]:
    policy = load_json(policy_json)
    if not isinstance(policy, dict):
        raise ValueError(f"policy JSON is not an object: {policy_json}")
    if policy.get("status") != POLICY_STATUS:
        raise ValueError(f"policy status must be {POLICY_STATUS}")
    summary = policy.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("policy summary is missing")
    if summary.get("packet_row_count") != EXPECTED_DBN_ROWS:
        raise ValueError(f"policy must have {EXPECTED_DBN_ROWS} packet rows")
    if summary.get("status_equality_all_decoded_records_match") is not True:
        raise ValueError("status equality proof is not passing")
    counts = summary.get("policy_decision_counts")
    if counts != EXPECTED_DECISION_COUNTS:
        raise ValueError(f"unexpected policy decision counts: {counts}")
    rows = policy.get("rows")
    if not isinstance(rows, list):
        raise ValueError("policy rows are missing")
    if len(rows) != EXPECTED_DBN_ROWS:
        raise ValueError(f"expected {EXPECTED_DBN_ROWS} policy rows")
    return rows


def build_actions(repo_root: Path, rows: list[dict[str, Any]], archive_root: Path) -> list[dict[str, Any]]:
    row_keys: set[tuple[str, int, str]] = set()
    actions: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"policy row {index} is not an object")
        decision = str(row.get("policy_decision") or "")
        if decision not in ARCHIVE_DECISIONS:
            raise ValueError(f"policy row {index} is not an archive candidate: {decision}")
        market = str(row.get("market") or "")
        year = int(row.get("year") or 0)
        schema_key = str(row.get("schema_key") or "")
        row_key = (market, year, schema_key)
        if row_key in row_keys:
            raise ValueError(f"duplicate market/year/schema row: {row_key}")
        if row_key in PROTECTED_ROW_KEYS:
            raise ValueError(f"protected SR active-lineage row selected: {row_key}")
        row_keys.add(row_key)
        decision_counts[decision] += 1

        parent_path_text = str(row.get("parent_path") or "").replace("\\", "/")
        parent_sha256 = str(row.get("parent_sha256") or "")
        require_safe_relative_path(parent_path_text)
        source = repo_path(repo_root, parent_path_text)
        manifest = dbn_manifest_path(source)
        source_manifest_text = rel(manifest, repo_root)
        target = repo_path(repo_root, archive_root) / parent_path_text
        target_manifest = dbn_manifest_path(target)

        if not source.is_file():
            raise ValueError(f"source DBN missing: {parent_path_text}")
        if not manifest.is_file():
            raise ValueError(f"source manifest missing: {source_manifest_text}")
        actual_sha = sha256_file(source)
        if actual_sha != parent_sha256:
            raise ValueError(
                f"source DBN hash mismatch for {parent_path_text}: "
                f"expected {parent_sha256}, actual {actual_sha}"
            )
        manifest_sha = sha256_file(manifest)
        if target.exists():
            raise ValueError(f"destination DBN already exists: {rel(target, repo_root)}")
        if target_manifest.exists():
            raise ValueError(
                f"destination manifest already exists: {rel(target_manifest, repo_root)}"
            )

        actions.append(
            {
                "market": market,
                "year": year,
                "schema_key": schema_key,
                "policy_decision": decision,
                "source": parent_path_text,
                "source_sha256": actual_sha,
                "source_bytes": source.stat().st_size,
                "source_manifest": source_manifest_text,
                "source_manifest_sha256": manifest_sha,
                "source_manifest_bytes": manifest.stat().st_size,
                "destination": rel(target, repo_root),
                "destination_manifest": rel(target_manifest, repo_root),
            }
        )

    if len(actions) != EXPECTED_DBN_ROWS:
        raise ValueError(f"expected {EXPECTED_DBN_ROWS} DBN move actions")
    if dict(sorted(decision_counts.items())) != EXPECTED_DECISION_COUNTS:
        raise ValueError(f"unexpected action decision counts: {dict(decision_counts)}")
    if len(actions) * 2 != EXPECTED_FILE_COUNT:
        raise ValueError(f"expected {EXPECTED_FILE_COUNT} DBN+manifest files")
    return actions


def execute_actions(repo_root: Path, actions: list[dict[str, Any]]) -> None:
    for action in actions:
        source = repo_path(repo_root, action["source"])
        manifest = repo_path(repo_root, action["source_manifest"])
        destination = repo_path(repo_root, action["destination"])
        destination_manifest = repo_path(repo_root, action["destination_manifest"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        shutil.move(str(manifest), str(destination_manifest))
        if sha256_file(destination) != action["source_sha256"]:
            raise ValueError(f"destination DBN hash mismatch: {action['destination']}")
        if sha256_file(destination_manifest) != action["source_manifest_sha256"]:
            raise ValueError(
                f"destination manifest hash mismatch: {action['destination_manifest']}"
            )
        if source.exists() or manifest.exists():
            raise ValueError(f"source still exists after move: {action['source']}")


def verify_exclusions(repo_root: Path) -> dict[str, Any]:
    protected_sidecar = repo_root / "data/dbn/sr1_sr3_2020_parent_sidecar_staging_20260705"
    protected_sr_parent = [
        repo_root / "data/dbn/ohlcv_1m_parent/SR1/2020/2020-01-01_2021-01-01.dbn.zst",
        repo_root / "data/dbn/ohlcv_1m_parent/SR3/2020/2020-01-01_2021-01-01.dbn.zst",
    ]
    sidecar_files = (
        sorted(path for path in protected_sidecar.rglob("*") if path.is_file())
        if protected_sidecar.exists()
        else []
    )
    return {
        "protected_sidecar_root_exists": protected_sidecar.is_dir(),
        "protected_sidecar_file_count": len(sidecar_files),
        "protected_sr_parent_sources": [
            {"path": rel(path, repo_root), "exists": path.is_file()}
            for path in protected_sr_parent
        ],
    }


def build_report(
    *,
    repo_root: Path,
    policy_json: Path,
    archive_root: Path,
    report_json: Path,
    report_md: Path,
    execute: bool,
) -> dict[str, Any]:
    rows = load_policy_rows(policy_json)
    actions = build_actions(repo_root, rows, archive_root)
    if execute:
        execute_actions(repo_root, actions)
    status = "ARCHIVED" if execute else "DRY_RUN_READY"
    report = {
        "stage": "dbn_parent_source_row_archive",
        "status": status,
        "generated_at_utc": utc_now(),
        "executed": execute,
        "policy_json": rel(policy_json, repo_root),
        "archive_root": rel(repo_path(repo_root, archive_root), repo_root),
        "report_json": rel(report_json, repo_root),
        "report_md": rel(report_md, repo_root),
        "bounds": {
            "expected_dbn_rows": EXPECTED_DBN_ROWS,
            "expected_file_count_including_manifests": EXPECTED_FILE_COUNT,
            "forbidden_provider_calls": True,
            "forbidden_deletes": True,
            "forbidden_promotions": True,
            "forbidden_sidecar_canonicalization": True,
            "forbidden_downstream_rebuilds": True,
        },
        "summary": {
            "dbn_row_count": len(actions),
            "file_count_including_manifests": len(actions) * 2,
            "policy_decision_counts": dict(
                sorted(Counter(action["policy_decision"] for action in actions).items())
            ),
            "root_counts": dict(
                sorted(
                    Counter(action["source"].split("/", 3)[2] for action in actions).items()
                )
            ),
            "market_counts": dict(
                sorted(Counter(action["market"] for action in actions).items())
            ),
            "schema_counts": dict(
                sorted(Counter(action["schema_key"] for action in actions).items())
            ),
        },
        "exclusion_verification": verify_exclusions(repo_root),
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
    if summary["policy_decision_counts"] != EXPECTED_DECISION_COUNTS:
        raise ValueError("report policy decision counts mismatch")
    exclusion = report["exclusion_verification"]
    if not exclusion["protected_sidecar_root_exists"]:
        raise ValueError("protected SR sidecar staging root is missing")
    if exclusion["protected_sidecar_file_count"] != 8:
        raise ValueError("protected SR sidecar staging file count changed")
    if not all(row["exists"] for row in exclusion["protected_sr_parent_sources"]):
        raise ValueError("protected SR parent OHLCV source is missing")


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# DBN Parent-Source Row Archive",
        "",
        f"- Status: `{report['status']}`.",
        f"- Executed: `{report['executed']}`.",
        f"- Policy JSON: `{report['policy_json']}`.",
        f"- Archive root: `{report['archive_root']}`.",
        "",
        "## Bounds",
        "",
        f"- DBN rows: `{report['summary']['dbn_row_count']}`.",
        f"- Files including manifests: `{report['summary']['file_count_including_manifests']}`.",
        f"- Policy decision counts: `{json.dumps(report['summary']['policy_decision_counts'], sort_keys=True)}`.",
        f"- Root counts: `{json.dumps(report['summary']['root_counts'], sort_keys=True)}`.",
        f"- Market counts: `{json.dumps(report['summary']['market_counts'], sort_keys=True)}`.",
        f"- Schema counts: `{json.dumps(report['summary']['schema_counts'], sort_keys=True)}`.",
        "",
        "## Exclusions",
        "",
        f"- Protected SR sidecar root exists: `{report['exclusion_verification']['protected_sidecar_root_exists']}`.",
        f"- Protected SR sidecar file count: `{report['exclusion_verification']['protected_sidecar_file_count']}`.",
        "- Protected SR parent OHLCV rows:",
    ]
    for row in report["exclusion_verification"]["protected_sr_parent_sources"]:
        lines.append(f"  - `{row['path']}` exists: `{row['exists']}`.")
    lines.extend(
        [
            "",
            "## Actions",
            "",
            "| Market | Year | Schema | Decision | Source | Destination |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for action in report["actions"]:
        lines.append(
            "| `{market}` | `{year}` | `{schema_key}` | `{policy_decision}` | `{source}` | `{destination}` |".format(
                **action
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy-json", default=DEFAULT_POLICY_JSON)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--report-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    policy_json = repo_path(repo_root, args.policy_json)
    archive_root = Path(args.archive_root)
    report_json = repo_path(repo_root, args.report_json)
    report_md = repo_path(repo_root, args.report_md)
    report = build_report(
        repo_root=repo_root,
        policy_json=policy_json,
        archive_root=archive_root,
        report_json=report_json,
        report_md=report_md,
        execute=args.execute,
    )
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
