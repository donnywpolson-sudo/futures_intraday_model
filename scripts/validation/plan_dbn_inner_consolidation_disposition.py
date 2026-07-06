"""Report-only disposition plan for non-final direct children under data/dbn."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCOPED_ROOTS = {
    "data/dbn/_promotion_staging": {
        "classification": "archive_evidence_candidate",
        "disposition": "archive_after_separate_approval",
        "proposed_future_destination": "archive/dbn_inner_consolidation_20260705/_promotion_staging",
        "rationale": "KE parent-lineage promotion staging evidence; active canonical targets now match staged promoted DBNs.",
        "required_before_any_change": "Separate bounded move approval, fresh hash verification, and post-move raw/DBN alignment.",
    },
    "data/dbn/_archive_parent_consolidation": {
        "classification": "archive_evidence_candidate",
        "disposition": "archive_after_separate_approval",
        "proposed_future_destination": "archive/dbn_inner_consolidation_20260705/_archive_parent_consolidation",
        "rationale": "Replaced canonical KE DBN evidence from approved parent-lineage promotion; not an active download folder.",
        "required_before_any_change": "Separate bounded move approval, fresh hash verification, and post-move raw/DBN alignment.",
    },
    "data/dbn/sr1_sr3_2020_parent_sidecar_staging_20260705": {
        "classification": "protect_active_lineage",
        "disposition": "protect_no_touch",
        "proposed_future_destination": "",
        "rationale": "Active SR1/SR3 2020 raw lineage still references staged parent status/statistics sidecars.",
        "required_before_any_change": "Separate sidecar canonicalization/archive decision with exact paths, hashes, destination policy, no-touch set, and validation.",
    },
    "data/dbn/ohlcv_1m_parent": {
        "classification": "review_required_parent_source",
        "disposition": "protect_no_touch",
        "proposed_future_destination": "",
        "rationale": "Parent-source rows remain unresolved; only exact approved rows may be promoted or archived.",
        "required_before_any_change": "Explicit parent-source decision packet approving exact market/year/schema rows.",
    },
    "data/dbn/statistics_parent": {
        "classification": "review_required_parent_source",
        "disposition": "protect_no_touch",
        "proposed_future_destination": "",
        "rationale": "Parent-source rows remain unresolved; only exact approved rows may be promoted or archived.",
        "required_before_any_change": "Explicit parent-source decision packet approving exact market/year/schema rows.",
    },
    "data/dbn/status_parent": {
        "classification": "review_required_parent_source",
        "disposition": "protect_no_touch",
        "proposed_future_destination": "",
        "rationale": "Parent-source rows remain unresolved; only exact approved rows may be promoted or archived.",
        "required_before_any_change": "Explicit parent-source decision packet approving exact market/year/schema rows.",
    },
}

FINAL_ALLOWED_DBN_CHILDREN = [
    "definition",
    "ohlcv_1d",
    "ohlcv_1h",
    "ohlcv_1m",
    "ohlcv_1s",
    "statistics",
    "status",
    "trades",
]


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
    file_rows = []
    aggregate = hashlib.sha256()
    total_bytes = 0
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


def recommendation_counts(decisions: dict[str, Any]) -> Counter[str]:
    return Counter(row.get("recommendation", "") for row in decisions.get("decisions", []))


def parent_recommendations_for_root(decisions: dict[str, Any], root: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    prefix = root.rstrip("/") + "/"
    for row in decisions.get("decisions", []):
        parent_path = str(row.get("parent_path", ""))
        if parent_path == root or parent_path.startswith(prefix):
            counts[str(row.get("recommendation", ""))] += 1
    return dict(sorted(counts.items()))


def verify_promotion(promote: dict[str, Any], validate: dict[str, Any]) -> dict[str, Any]:
    actions = promote.get("actions", [])
    staged_target_checks = []
    archive_checks = []
    for action in actions:
        staged = Path(action["staged"])
        target = Path(action["target"])
        archive = Path(action["archive"])
        staged_sha = file_sha256(staged) if staged.exists() else ""
        target_sha = file_sha256(target) if target.exists() else ""
        archive_sha = file_sha256(archive) if archive.exists() else ""
        staged_target_checks.append(
            {
                "staged": rel(staged),
                "target": rel(target),
                "staged_exists": staged.exists(),
                "target_exists": target.exists(),
                "staged_sha256": staged_sha,
                "target_sha256": target_sha,
                "staged_matches_target": bool(staged_sha and staged_sha == target_sha),
            }
        )
        archive_checks.append(
            {
                "archive": rel(archive),
                "archive_exists": archive.exists(),
                "archive_sha256": archive_sha,
            }
        )
    return {
        "promote_executed": promote.get("executed") is True,
        "promote_approved_row_count": promote.get("approved_row_count"),
        "promote_action_count": len(actions),
        "validate_status": validate.get("status"),
        "validate_failures": validate.get("failures", []),
        "validate_approved_row_count": validate.get("approved_row_count"),
        "staged_targets_all_match": all(row["staged_matches_target"] for row in staged_target_checks),
        "archive_files_all_exist": all(row["archive_exists"] for row in archive_checks),
        "staged_target_checks": staged_target_checks,
        "archive_checks": archive_checks,
    }


def verify_sr_lineage(sr: dict[str, Any]) -> dict[str, Any]:
    rows = []
    root = "data/dbn/sr1_sr3_2020_parent_sidecar_staging_20260705/"
    for source_row in sr.get("rows", []):
        for key in ("statistics", "status"):
            paths = source_row.get(f"{key}_source_paths", [])
            hashes = set(source_row.get(f"{key}_source_hashes", []))
            for path_text in paths:
                if not path_text.startswith(root):
                    continue
                path = Path(path_text)
                digest = file_sha256(path) if path.exists() else ""
                rows.append(
                    {
                        "market": source_row.get("market"),
                        "year": source_row.get("year"),
                        "schema": key,
                        "path": path_text,
                        "exists": path.exists(),
                        "sha256": digest,
                        "hash_matches_replacement_report": bool(digest and digest in hashes),
                    }
                )
    return {
        "replacement_status": sr.get("status"),
        "replacement_failures": sr.get("failures", []),
        "sidecar_canonicalization_performed": sr.get("policy", {}).get("sidecar_canonicalization"),
        "referenced_staged_sidecar_count": len(rows),
        "all_referenced_staged_sidecars_exist": all(row["exists"] for row in rows),
        "all_referenced_staged_sidecar_hashes_match": all(
            row["hash_matches_replacement_report"] for row in rows
        ),
        "referenced_staged_sidecars": rows,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    promote = load_json(Path(args.promotion_json))
    validate = load_json(Path(args.validation_json))
    sr = load_json(Path(args.sr_replacement_json))
    decisions = load_json(Path(args.decisions_json))

    dbn_root = Path(args.dbn_root)
    direct_children = sorted([p.name for p in dbn_root.iterdir() if p.is_dir()])
    scoped_child_names = sorted(Path(root).name for root in SCOPED_ROOTS)
    unexpected_non_final = sorted(
        name
        for name in direct_children
        if name not in FINAL_ALLOWED_DBN_CHILDREN and name not in scoped_child_names
    )

    rows = []
    for root_text, meta in SCOPED_ROOTS.items():
        row = {
            "root": root_text,
            **meta,
            "approved_action": "none",
            "inventory": tree_inventory(Path(root_text)),
        }
        if meta["classification"] == "review_required_parent_source":
            row["parent_source_recommendation_counts"] = parent_recommendations_for_root(
                decisions, root_text
            )
        rows.append(row)

    promotion = verify_promotion(promote, validate)
    sr_lineage = verify_sr_lineage(sr)
    recommendation_summary = dict(sorted(recommendation_counts(decisions).items()))

    evidence_pass = (
        promotion["promote_executed"]
        and promotion["promote_approved_row_count"] == 12
        and promotion["promote_action_count"] == 12
        and promotion["validate_status"] == "PASS"
        and not promotion["validate_failures"]
        and promotion["staged_targets_all_match"]
        and promotion["archive_files_all_exist"]
        and sr_lineage["replacement_status"] == "PASS"
        and not sr_lineage["replacement_failures"]
        and sr_lineage["sidecar_canonicalization_performed"] is False
        and sr_lineage["referenced_staged_sidecar_count"] == 4
        and sr_lineage["all_referenced_staged_sidecars_exist"]
        and sr_lineage["all_referenced_staged_sidecar_hashes_match"]
        and recommendation_summary.get("promote_parent") == 12
        and recommendation_summary.get("review_required") == 112
        and recommendation_summary.get("keep_canonical") == 19
        and len(decisions.get("decisions", [])) == 143
        and not unexpected_non_final
    )

    return {
        "stage": "dbn_inner_consolidation_disposition_plan",
        "status": "PASS_PLAN_READY_NO_EXECUTION" if evidence_pass else "WARN_REVIEW_REQUIRED_NO_EXECUTION",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "report-only disposition for six non-final direct children under data/dbn",
        "non_approval": {
            "file_moves": False,
            "file_deletes": False,
            "data_mutation": False,
            "provider_network_calls": False,
            "sidecar_canonicalization": False,
            "raw_causal_label_feature_wfa_prediction_modeling": False,
            "commit_push_paper_live": False,
        },
        "final_allowed_dbn_children": FINAL_ALLOWED_DBN_CHILDREN,
        "current_direct_dbn_children": direct_children,
        "scoped_non_final_children": scoped_child_names,
        "unexpected_non_final_children": unexpected_non_final,
        "recommended_later_archive_root": "archive/dbn_inner_consolidation_20260705",
        "input_evidence": {
            "promotion_json": args.promotion_json,
            "validation_json": args.validation_json,
            "sr_replacement_json": args.sr_replacement_json,
            "decisions_json": args.decisions_json,
        },
        "evidence_checks": {
            "ke_promotion": promotion,
            "sr_sidecar_dependency": sr_lineage,
            "parent_decision_summary": {
                "decision_count": len(decisions.get("decisions", [])),
                "recommendation_counts": recommendation_summary,
                "approval_template_count": decisions.get("summary", {}).get("approval_template_count"),
            },
        },
        "rows": rows,
        "summary": {
            "root_count": len(rows),
            "classification_counts": dict(Counter(row["classification"] for row in rows)),
            "approved_file_moves": 0,
            "approved_file_deletes": 0,
            "approved_data_mutations": 0,
            "archive_evidence_candidate_count": sum(
                1 for row in rows if row["classification"] == "archive_evidence_candidate"
            ),
            "protect_active_lineage_count": sum(
                1 for row in rows if row["classification"] == "protect_active_lineage"
            ),
            "review_required_parent_source_count": sum(
                1 for row in rows if row["classification"] == "review_required_parent_source"
            ),
        },
        "recommended_next_step": (
            "If cleanup is still desired, request a bounded move-only execution plan for only "
            "the two archive_evidence_candidate roots; keep SR sidecar staging and parent-source "
            "roots untouched until separate sidecar or parent-source decisions exist."
        ),
    }


def write_markdown(report: dict[str, Any], md_out: Path) -> None:
    lines = [
        "# DBN Inner Consolidation Disposition",
        "",
        f"- Status: `{report['status']}`.",
        "- Scope: six non-final direct children under `data/dbn`.",
        "- Approved moves/deletes/data mutations: `0`.",
        f"- Recommended later archive root: `{report['recommended_later_archive_root']}`.",
        "",
        "## Evidence",
        "",
        f"- KE promotion executed: `{report['evidence_checks']['ke_promotion']['promote_executed']}`.",
        f"- KE approved/promotion action rows: `{report['evidence_checks']['ke_promotion']['promote_approved_row_count']}` / `{report['evidence_checks']['ke_promotion']['promote_action_count']}`.",
        f"- KE validation status: `{report['evidence_checks']['ke_promotion']['validate_status']}`.",
        f"- KE staged targets all match active targets: `{report['evidence_checks']['ke_promotion']['staged_targets_all_match']}`.",
        f"- KE archive files all exist: `{report['evidence_checks']['ke_promotion']['archive_files_all_exist']}`.",
        f"- SR replacement status: `{report['evidence_checks']['sr_sidecar_dependency']['replacement_status']}`.",
        f"- SR referenced staged sidecars: `{report['evidence_checks']['sr_sidecar_dependency']['referenced_staged_sidecar_count']}`.",
        f"- Parent decision counts: `{json.dumps(report['evidence_checks']['parent_decision_summary']['recommendation_counts'], sort_keys=True)}`.",
        "",
        "## Current DBN Children",
        "",
        "| Child | Final allowed? |",
        "|---|---:|",
    ]
    for child in report["current_direct_dbn_children"]:
        lines.append(f"| `{child}` | `{child in FINAL_ALLOWED_DBN_CHILDREN}` |")
    lines.extend(
        [
            "",
            "## Disposition Rows",
            "",
            "| Root | Files | DBN | Manifests | Bytes | Classification | Disposition | Tree SHA-256 |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in report["rows"]:
        inv = row["inventory"]
        lines.append(
            "| `{root}` | {files} | {dbn} | {manifests} | {bytes} | `{cls}` | `{disp}` | `{sha}` |".format(
                root=row["root"],
                files=inv["files"],
                dbn=inv["dbn_zst_files"],
                manifests=inv["manifest_files"],
                bytes=inv["bytes"],
                cls=row["classification"],
                disp=row["disposition"],
                sha=inv["tree_sha256"],
            )
        )
    lines.extend(
        [
            "",
            "## Required Before Any Change",
            "",
            "| Root | Requirement |",
            "|---|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(f"| `{row['root']}` | {row['required_before_any_change']} |")
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "This report performs and approves no file moves, file deletes, data mutation, provider/network calls, sidecar canonicalization, downstream rebuilds, commits, pushes, paper trading, or live work.",
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
    parser.add_argument("--dbn-root", default="data/dbn")
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
        "--decisions-json",
        default="reports/data_audit/he_ke_le_dbn_parent_consolidation_decisions.json",
    )
    parser.add_argument(
        "--json-out",
        default="reports/data_audit/current_state/dbn_inner_consolidation_disposition_20260705.json",
    )
    parser.add_argument(
        "--md-out",
        default="reports/data_audit/current_state/dbn_inner_consolidation_disposition_20260705.md",
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
    print(json.dumps({"status": report["status"], "json_out": rel(json_out), "md_out": rel(md_out)}))
    return 0 if report["status"] == "PASS_PLAN_READY_NO_EXECUTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
