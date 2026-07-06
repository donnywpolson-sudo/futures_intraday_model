"""Report-only disposition refresh for DBN parent-source roots."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCOPED_ROOTS = {
    "data/dbn/ohlcv_1m_parent": "ohlcv_1m",
    "data/dbn/statistics_parent": "statistics",
    "data/dbn/status_parent": "status",
}

EXPECTED_CLASSIFICATION_COUNTS = {
    "protect_active_lineage": 2,
    "already_promoted_or_excluded_from_parent_cleanup": 12,
    "review_required_parent_source": 112,
}


def rel(path: Path) -> str:
    return path.as_posix()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_inventory(root: Path) -> dict[str, Any]:
    exists = root.exists()
    files = sorted([p for p in root.rglob("*") if p.is_file()]) if exists else []
    dirs = sorted([p for p in root.rglob("*") if p.is_dir()]) if exists else []
    total_bytes = 0
    aggregate = hashlib.sha256()
    file_rows = []

    for path in files:
        digest = file_sha256(path)
        size = path.stat().st_size
        total_bytes += size
        rel_path = rel(path)
        file_rows.append({"path": rel_path, "bytes": size, "sha256": digest})
        aggregate.update(rel_path.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")

    return {
        "exists": exists,
        "dirs": len(dirs),
        "files": len(files),
        "dbn_zst_files": sum(1 for p in files if p.name.endswith(".dbn.zst")),
        "manifest_files": sum(1 for p in files if p.name.endswith(".manifest.json")),
        "other_files": sum(
            1
            for p in files
            if not p.name.endswith(".dbn.zst") and not p.name.endswith(".manifest.json")
        ),
        "bytes": total_bytes,
        "tree_sha256": aggregate.hexdigest(),
        "file_hashes": file_rows,
    }


def parse_parent_path(path: Path, root: Path, schema_key: str) -> dict[str, Any]:
    parts = path.relative_to(root).parts
    if schema_key == "ohlcv_1m":
        market, year = parts[0], int(parts[1])
    else:
        market, year = parts[1], int(parts[2])
    return {"market": market, "year": year, "schema_key": schema_key}


def decision_lookup(decisions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("parent_path", "")): row for row in decisions.get("decisions", [])}


def active_lineage_lookup(sr_replacement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for source_row in sr_replacement.get("rows", []):
        for path_text in source_row.get("ohlcv_source_paths", []):
            if not path_text.startswith("data/dbn/ohlcv_1m_parent/"):
                continue
            rows[path_text] = {
                "market": source_row.get("market"),
                "year": source_row.get("year"),
                "raw_path": source_row.get("raw_path"),
                "raw_sha256": source_row.get("raw_sha256"),
                "expected_source_hashes": source_row.get("ohlcv_source_hashes", []),
                "raw_matches_manifest": source_row.get("raw_matches_manifest"),
                "raw_matches_staged": source_row.get("raw_matches_staged"),
                "rows": source_row.get("rows"),
            }
    return rows


def promotion_action_targets(promote: dict[str, Any]) -> set[str]:
    return {str(row.get("target", "")) for row in promote.get("actions", [])}


def classify_row(
    path_text: str,
    digest: str,
    decision: dict[str, Any] | None,
    active_lineage: dict[str, Any] | None,
    promotion_targets: set[str],
) -> tuple[str, str]:
    if active_lineage is not None:
        if digest in set(active_lineage.get("expected_source_hashes", [])):
            return "protect_active_lineage", "referenced_by_active_sr1_sr3_2020_raw_lineage"
        return "review_required_parent_source", "active_lineage_path_hash_mismatch"

    if decision and decision.get("recommendation") == "promote_parent":
        canonical_target = str(decision.get("canonical_target_path", ""))
        if canonical_target in promotion_targets:
            return (
                "already_promoted_or_excluded_from_parent_cleanup",
                "approved_ke_parent_row_already_promoted_to_canonical",
            )
        return "review_required_parent_source", "promote_parent_row_missing_promotion_target_evidence"

    return "review_required_parent_source", "no_explicit_parent_source_disposition"


def build_parent_rows(
    decisions: dict[str, Any],
    sr_replacement: dict[str, Any],
    promote: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions_by_parent_path = decision_lookup(decisions)
    active_by_path = active_lineage_lookup(sr_replacement)
    target_paths = promotion_action_targets(promote)
    rows: list[dict[str, Any]] = []

    for root_text, schema_key in SCOPED_ROOTS.items():
        root = Path(root_text)
        for dbn_path in sorted(root.rglob("*.dbn.zst")):
            path_text = rel(dbn_path)
            digest = file_sha256(dbn_path)
            manifest = Path(path_text + ".manifest.json")
            decision = decisions_by_parent_path.get(path_text)
            active_lineage = active_by_path.get(path_text)
            classification, reason = classify_row(
                path_text=path_text,
                digest=digest,
                decision=decision,
                active_lineage=active_lineage,
                promotion_targets=target_paths,
            )

            parsed = parse_parent_path(dbn_path, root, schema_key)
            canonical_target = decision.get("canonical_target_path") if decision else ""
            canonical_target_hash = ""
            canonical_target_matches_parent = False
            if canonical_target and Path(canonical_target).exists():
                canonical_target_hash = file_sha256(Path(canonical_target))
                canonical_target_matches_parent = canonical_target_hash == digest

            rows.append(
                {
                    **parsed,
                    "root": root_text,
                    "path": path_text,
                    "bytes": dbn_path.stat().st_size,
                    "sha256": digest,
                    "manifest_path": rel(manifest),
                    "manifest_exists": manifest.exists(),
                    "manifest_sha256": file_sha256(manifest) if manifest.exists() else "",
                    "source_decision_recommendation": decision.get("recommendation") if decision else "",
                    "source_decision_classification": decision.get("classification") if decision else "",
                    "source_decision_parent_sha256": decision.get("parent_sha256") if decision else "",
                    "source_decision_parent_hash_matches_current": bool(
                        decision and decision.get("parent_sha256") == digest
                    ),
                    "canonical_target_path": canonical_target,
                    "canonical_target_sha256": canonical_target_hash,
                    "canonical_target_matches_parent": canonical_target_matches_parent,
                    "active_lineage": active_lineage or {},
                    "classification": classification,
                    "classification_reason": reason,
                }
            )

    return rows


def verify_ke_promoted_rows(rows: list[dict[str, Any]], promote: dict[str, Any], validate: dict[str, Any]) -> dict[str, Any]:
    promoted_rows = [
        row
        for row in rows
        if row["classification"] == "already_promoted_or_excluded_from_parent_cleanup"
    ]
    return {
        "promotion_executed": promote.get("executed") is True,
        "promotion_approved_row_count": promote.get("approved_row_count"),
        "promotion_action_count": len(promote.get("actions", [])),
        "validation_status": validate.get("status"),
        "validation_approved_row_count": validate.get("approved_row_count"),
        "validation_failure_count": len(validate.get("failures", [])),
        "classified_promoted_row_count": len(promoted_rows),
        "all_promoted_rows_parent_hash_match_decision": all(
            row["source_decision_parent_hash_matches_current"] for row in promoted_rows
        ),
        "all_promoted_rows_canonical_target_match_parent": all(
            row["canonical_target_matches_parent"] for row in promoted_rows
        ),
        "promoted_rows": [
            {
                "market": row["market"],
                "year": row["year"],
                "schema_key": row["schema_key"],
                "parent_path": row["path"],
                "canonical_target_path": row["canonical_target_path"],
                "sha256": row["sha256"],
            }
            for row in promoted_rows
        ],
    }


def verify_sr_active_lineage(rows: list[dict[str, Any]], sr_replacement: dict[str, Any]) -> dict[str, Any]:
    protected_rows = [row for row in rows if row["classification"] == "protect_active_lineage"]
    return {
        "replacement_status": sr_replacement.get("status"),
        "replacement_failure_count": len(sr_replacement.get("failures", [])),
        "classified_active_lineage_row_count": len(protected_rows),
        "all_active_lineage_hashes_match_report": all(
            row["sha256"] in set(row["active_lineage"].get("expected_source_hashes", []))
            for row in protected_rows
        ),
        "active_lineage_rows": [
            {
                "market": row["market"],
                "year": row["year"],
                "schema_key": row["schema_key"],
                "path": row["path"],
                "sha256": row["sha256"],
                "raw_path": row["active_lineage"].get("raw_path"),
                "raw_sha256": row["active_lineage"].get("raw_sha256"),
                "raw_rows": row["active_lineage"].get("rows"),
            }
            for row in protected_rows
        ],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    decisions = load_json(Path(args.decisions_json))
    promote = load_json(Path(args.promotion_json))
    validate = load_json(Path(args.validation_json))
    sr_replacement = load_json(Path(args.sr_replacement_json))

    inventories = {root: tree_inventory(Path(root)) for root in SCOPED_ROOTS}
    rows = build_parent_rows(decisions, sr_replacement, promote)
    classification_counts = dict(sorted(Counter(row["classification"] for row in rows).items()))
    root_counts = {
        root: dict(sorted(Counter(row["classification"] for row in rows if row["root"] == root).items()))
        for root in SCOPED_ROOTS
    }
    decision_counts = dict(
        sorted(Counter(row.get("recommendation", "") for row in decisions.get("decisions", [])).items())
    )
    ke_check = verify_ke_promoted_rows(rows, promote, validate)
    sr_check = verify_sr_active_lineage(rows, sr_replacement)
    missing_manifests = [row["path"] for row in rows if not row["manifest_exists"]]

    evidence_pass = (
        all(inv["exists"] for inv in inventories.values())
        and sum(inv["dbn_zst_files"] for inv in inventories.values()) == 126
        and not missing_manifests
        and classification_counts == EXPECTED_CLASSIFICATION_COUNTS
        and decision_counts.get("promote_parent") == 12
        and decision_counts.get("review_required") == 112
        and decision_counts.get("keep_canonical") == 19
        and ke_check["promotion_executed"]
        and ke_check["promotion_approved_row_count"] == 12
        and ke_check["promotion_action_count"] == 12
        and ke_check["validation_status"] == "PASS"
        and ke_check["validation_failure_count"] == 0
        and ke_check["classified_promoted_row_count"] == 12
        and ke_check["all_promoted_rows_parent_hash_match_decision"]
        and ke_check["all_promoted_rows_canonical_target_match_parent"]
        and sr_check["replacement_status"] == "PASS"
        and sr_check["replacement_failure_count"] == 0
        and sr_check["classified_active_lineage_row_count"] == 2
        and sr_check["all_active_lineage_hashes_match_report"]
    )

    return {
        "stage": "dbn_parent_source_disposition_refresh",
        "status": "PASS_PARENT_SOURCE_DISPOSITION_READY_NO_EXECUTION"
        if evidence_pass
        else "WARN_PARENT_SOURCE_DISPOSITION_REVIEW_REQUIRED_NO_EXECUTION",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "report-only disposition refresh for data/dbn parent-source roots",
        "scoped_roots": list(SCOPED_ROOTS),
        "non_approval": {
            "file_moves": False,
            "file_deletes": False,
            "provider_network_calls": False,
            "sidecar_canonicalization": False,
            "parent_source_promotion": False,
            "raw_causal_label_feature_wfa_prediction_modeling": False,
            "commit_push_paper_live": False,
        },
        "input_evidence": {
            "decisions_json": args.decisions_json,
            "promotion_json": args.promotion_json,
            "validation_json": args.validation_json,
            "sr_replacement_json": args.sr_replacement_json,
        },
        "summary": {
            "parent_dbn_row_count": len(rows),
            "classification_counts": classification_counts,
            "root_classification_counts": root_counts,
            "decision_recommendation_counts": decision_counts,
            "missing_manifest_count": len(missing_manifests),
            "approved_file_moves": 0,
            "approved_file_deletes": 0,
            "approved_data_mutations": 0,
        },
        "inventories": inventories,
        "evidence_checks": {
            "ke_promoted_rows": ke_check,
            "sr_active_lineage": sr_check,
        },
        "rows": rows,
        "recommended_next_step": (
            "If DBN parent-source cleanup is still desired, prepare a bounded report-only "
            "decision packet for the 112 review_required_parent_source rows; keep protected "
            "SR1/SR3 active-lineage rows and already-promoted KE rows untouched until a later "
            "explicit move or archive approval exists."
        ),
    }


def write_markdown(report: dict[str, Any], md_out: Path) -> None:
    lines = [
        "# DBN Parent-Source Disposition Refresh",
        "",
        f"- Status: `{report['status']}`.",
        "- Scope: `data/dbn/ohlcv_1m_parent`, `data/dbn/statistics_parent`, and `data/dbn/status_parent`.",
        "- Approved moves/deletes/data mutations: `0`.",
        "- Provider calls, sidecar canonicalization, parent-source promotion, downstream rebuilds, commits, pushes, paper, and live work: `none`.",
        "",
        "## Summary",
        "",
        f"- Parent DBN rows: `{report['summary']['parent_dbn_row_count']}`.",
        f"- Classification counts: `{json.dumps(report['summary']['classification_counts'], sort_keys=True)}`.",
        f"- Decision recommendation counts: `{json.dumps(report['summary']['decision_recommendation_counts'], sort_keys=True)}`.",
        f"- Missing manifests: `{report['summary']['missing_manifest_count']}`.",
        "",
        "## Evidence Checks",
        "",
        f"- SR replacement status: `{report['evidence_checks']['sr_active_lineage']['replacement_status']}`.",
        f"- SR active-lineage parent rows: `{report['evidence_checks']['sr_active_lineage']['classified_active_lineage_row_count']}`.",
        f"- SR active-lineage hashes match report: `{report['evidence_checks']['sr_active_lineage']['all_active_lineage_hashes_match_report']}`.",
        f"- KE promotion executed: `{report['evidence_checks']['ke_promoted_rows']['promotion_executed']}`.",
        f"- KE promotion/validation rows: `{report['evidence_checks']['ke_promoted_rows']['promotion_approved_row_count']}` / `{report['evidence_checks']['ke_promoted_rows']['validation_approved_row_count']}`.",
        f"- KE promoted rows classified: `{report['evidence_checks']['ke_promoted_rows']['classified_promoted_row_count']}`.",
        f"- KE promoted parent hashes match decision packet: `{report['evidence_checks']['ke_promoted_rows']['all_promoted_rows_parent_hash_match_decision']}`.",
        f"- KE promoted canonical targets match parent hashes: `{report['evidence_checks']['ke_promoted_rows']['all_promoted_rows_canonical_target_match_parent']}`.",
        "",
        "## Inventory",
        "",
        "| Root | Files | DBN | Manifests | Bytes | Tree SHA-256 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for root, inv in report["inventories"].items():
        lines.append(
            f"| `{root}` | {inv['files']} | {inv['dbn_zst_files']} | {inv['manifest_files']} | {inv['bytes']} | `{inv['tree_sha256']}` |"
        )

    lines.extend(
        [
            "",
            "## Root Classification Counts",
            "",
            "| Root | Classification Counts |",
            "|---|---|",
        ]
    )
    for root, counts in report["summary"]["root_classification_counts"].items():
        lines.append(f"| `{root}` | `{json.dumps(counts, sort_keys=True)}` |")

    lines.extend(
        [
            "",
            "## Row Disposition",
            "",
            "| Classification | Root | Market | Year | Schema | Path |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            f"| `{row['classification']}` | `{row['root']}` | `{row['market']}` | `{row['year']}` | `{row['schema_key']}` | `{row['path']}` |"
        )

    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            report["recommended_next_step"],
            "",
        ]
    )
    md_out.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decisions-json",
        default="reports/data_audit/he_ke_le_dbn_parent_consolidation_decisions.json",
    )
    parser.add_argument(
        "--promotion-json",
        default="reports/data_audit/he_ke_le_dbn_parent_consolidation_promote_ke_parent_lineage.json",
    )
    parser.add_argument(
        "--validation-json",
        default="reports/data_audit/he_ke_le_dbn_parent_consolidation_validate_after_raw_replacement.json",
    )
    parser.add_argument(
        "--sr-replacement-json",
        default="reports/data_audit/sr1_sr3_2020_parent_sidecar_raw_replacement_20260705.json",
    )
    parser.add_argument(
        "--json-out",
        default="reports/data_audit/current_state/dbn_parent_source_disposition_20260705.json",
    )
    parser.add_argument(
        "--md-out",
        default="reports/data_audit/current_state/dbn_parent_source_disposition_20260705.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, md_out)
    print(
        json.dumps(
            {
                "status": report["status"],
                "json_out": rel(json_out),
                "md_out": rel(md_out),
                "classification_counts": report["summary"]["classification_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS_PARENT_SOURCE_DISPOSITION_READY_NO_EXECUTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
