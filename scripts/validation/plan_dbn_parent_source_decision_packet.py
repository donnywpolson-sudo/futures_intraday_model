"""Report-only row-decision packet for unresolved DBN parent-source rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_STATUS = "PASS_PARENT_SOURCE_DISPOSITION_READY_NO_EXECUTION"
PACKET_STATUS = "PASS_PARENT_SOURCE_DECISION_PACKET_READY_NO_EXECUTION"
REVIEW_CLASSIFICATION = "review_required_parent_source"
EXCLUDED_CLASSIFICATIONS = {
    "protect_active_lineage",
    "already_promoted_or_excluded_from_parent_cleanup",
}
PACKET_RECOMMENDATION = "decision_required_no_action"
EXPECTED_REVIEW_ROW_COUNT = 112


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


def verify_source_report(source: dict[str, Any]) -> None:
    if source.get("status") != SOURCE_STATUS:
        raise ValueError(f"source disposition status must be {SOURCE_STATUS}")
    counts = source.get("summary", {}).get("classification_counts", {})
    if counts.get(REVIEW_CLASSIFICATION) != EXPECTED_REVIEW_ROW_COUNT:
        raise ValueError(f"expected {EXPECTED_REVIEW_ROW_COUNT} review rows")
    for excluded in EXCLUDED_CLASSIFICATIONS:
        if counts.get(excluded, 0) <= 0:
            raise ValueError(f"source disposition missing excluded classification: {excluded}")


def make_packet_row(row: dict[str, Any]) -> dict[str, Any]:
    parent_path = Path(str(row["path"]))
    manifest_path = Path(str(row["manifest_path"]))
    if not parent_path.is_file():
        raise ValueError(f"parent DBN missing: {rel(parent_path)}")
    if not manifest_path.is_file():
        raise ValueError(f"parent manifest missing: {rel(manifest_path)}")

    parent_hash = file_sha256(parent_path)
    manifest_hash = file_sha256(manifest_path)
    if parent_hash != row.get("sha256"):
        raise ValueError(f"parent hash mismatch: {rel(parent_path)}")
    if manifest_hash != row.get("manifest_sha256"):
        raise ValueError(f"manifest hash mismatch: {rel(manifest_path)}")

    return {
        "market": row["market"],
        "year": row["year"],
        "schema_key": row["schema_key"],
        "root": row["root"],
        "parent_path": row["path"],
        "parent_sha256": parent_hash,
        "parent_bytes": parent_path.stat().st_size,
        "manifest_path": row["manifest_path"],
        "manifest_sha256": manifest_hash,
        "canonical_target_path": row.get("canonical_target_path", ""),
        "canonical_target_sha256": row.get("canonical_target_sha256", ""),
        "canonical_target_matches_parent": row.get("canonical_target_matches_parent"),
        "source_decision_recommendation": row.get("source_decision_recommendation", ""),
        "source_decision_classification": row.get("source_decision_classification", ""),
        "source_decision_parent_hash_matches_current": row.get(
            "source_decision_parent_hash_matches_current"
        ),
        "packet_recommendation": PACKET_RECOMMENDATION,
        "packet_reason": (
            "Parent and canonical DBNs differ, and this row has no active-lineage "
            "protection or approved promotion evidence in the current disposition report."
        ),
        "allowed_future_decisions": [
            "promote_parent_after_explicit_row_approval",
            "keep_canonical_archive_parent_candidate_after_explicit_row_approval",
            "blocked_pending_more_evidence",
        ],
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    source = load_json(Path(args.source_json))
    verify_source_report(source)
    rows = list(source.get("rows", []))
    review_rows = [row for row in rows if row.get("classification") == REVIEW_CLASSIFICATION]
    excluded_rows = [row for row in rows if row.get("classification") in EXCLUDED_CLASSIFICATIONS]
    unexpected_rows = [
        row
        for row in rows
        if row.get("classification") not in {REVIEW_CLASSIFICATION, *EXCLUDED_CLASSIFICATIONS}
    ]
    if len(review_rows) != EXPECTED_REVIEW_ROW_COUNT:
        raise ValueError(f"expected {EXPECTED_REVIEW_ROW_COUNT} packet rows")
    if unexpected_rows:
        raise ValueError("source disposition contains unexpected classifications")

    packet_rows = [make_packet_row(row) for row in review_rows]
    row_keys = [(row["market"], row["year"], row["schema_key"]) for row in packet_rows]
    if len(set(row_keys)) != len(row_keys):
        raise ValueError("duplicate market/year/schema rows in packet")

    excluded_summary = {
        classification: [
            {
                "market": row["market"],
                "year": row["year"],
                "schema_key": row["schema_key"],
                "path": row["path"],
                "reason": row.get("classification_reason", ""),
            }
            for row in excluded_rows
            if row.get("classification") == classification
        ]
        for classification in sorted(EXCLUDED_CLASSIFICATIONS)
    }

    root_counts = Counter(row["root"] for row in packet_rows)
    market_counts = Counter(row["market"] for row in packet_rows)
    schema_counts = Counter(row["schema_key"] for row in packet_rows)
    recommendation_counts = Counter(row["packet_recommendation"] for row in packet_rows)

    return {
        "stage": "dbn_parent_source_row_decision_packet",
        "status": PACKET_STATUS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_disposition": args.source_json,
        "scope": "report-only decision packet for review_required_parent_source rows",
        "non_approval": {
            "file_moves": False,
            "file_deletes": False,
            "provider_network_calls": False,
            "sidecar_canonicalization": False,
            "parent_source_promotion": False,
            "raw_causal_label_feature_wfa_prediction_modeling": False,
            "commit_push_paper_live": False,
        },
        "decision_contract": {
            "packet_rows_are_not_approved_for_execution": True,
            "wildcards_allowed": False,
            "future_approval_must_name_exact_market_year_schema_rows": True,
            "future_move_or_promotion_requires_separate_bounded_execution_approval": True,
            "allowed_future_decisions": [
                "promote_parent_after_explicit_row_approval",
                "keep_canonical_archive_parent_candidate_after_explicit_row_approval",
                "blocked_pending_more_evidence",
            ],
        },
        "summary": {
            "packet_row_count": len(packet_rows),
            "recommendation_counts": dict(sorted(recommendation_counts.items())),
            "root_counts": dict(sorted(root_counts.items())),
            "market_counts": dict(sorted(market_counts.items())),
            "schema_counts": dict(sorted(schema_counts.items())),
            "excluded_protect_active_lineage_count": len(
                excluded_summary.get("protect_active_lineage", [])
            ),
            "excluded_already_promoted_count": len(
                excluded_summary.get("already_promoted_or_excluded_from_parent_cleanup", [])
            ),
            "approved_file_moves": 0,
            "approved_file_deletes": 0,
            "approved_data_mutations": 0,
        },
        "excluded_rows": excluded_summary,
        "approval_template": {"approvals": []},
        "rows": packet_rows,
        "recommended_next_step": (
            "Review the 112 decision_required_no_action rows and choose exact "
            "market/year/schema decisions in a later prompt; no row is approved for "
            "promotion, archive, move, or deletion by this packet."
        ),
    }


def write_markdown(packet: dict[str, Any], md_out: Path) -> None:
    lines = [
        "# DBN Parent-Source Row Decision Packet",
        "",
        f"- Status: `{packet['status']}`.",
        f"- Source disposition: `{packet['source_disposition']}`.",
        "- Scope: 112 `review_required_parent_source` rows only.",
        "- Approved moves/deletes/data mutations: `0`.",
        "- Provider calls, sidecar canonicalization, parent-source promotion, downstream rebuilds, commits, pushes, paper, and live work: `none`.",
        "",
        "## Summary",
        "",
        f"- Packet rows: `{packet['summary']['packet_row_count']}`.",
        f"- Recommendation counts: `{json.dumps(packet['summary']['recommendation_counts'], sort_keys=True)}`.",
        f"- Root counts: `{json.dumps(packet['summary']['root_counts'], sort_keys=True)}`.",
        f"- Market counts: `{json.dumps(packet['summary']['market_counts'], sort_keys=True)}`.",
        f"- Schema counts: `{json.dumps(packet['summary']['schema_counts'], sort_keys=True)}`.",
        f"- Excluded protected active-lineage rows: `{packet['summary']['excluded_protect_active_lineage_count']}`.",
        f"- Excluded already-promoted rows: `{packet['summary']['excluded_already_promoted_count']}`.",
        "",
        "## Decision Contract",
        "",
        "- This packet approves no execution.",
        "- Future action must name exact market/year/schema rows; wildcards are not allowed.",
        "- Future promotion, archive, move, or delete work requires a separate bounded execution approval.",
        "",
        "## Packet Rows",
        "",
        "| Recommendation | Market | Year | Schema | Parent path | Canonical target |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in packet["rows"]:
        lines.append(
            "| `{packet_recommendation}` | `{market}` | `{year}` | `{schema_key}` | `{parent_path}` | `{canonical_target_path}` |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Excluded Rows",
            "",
            "| Classification | Count |",
            "|---|---:|",
        ]
    )
    for classification, rows in packet["excluded_rows"].items():
        lines.append(f"| `{classification}` | {len(rows)} |")

    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            packet["recommended_next_step"],
            "",
        ]
    )
    md_out.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-json",
        default="reports/data_audit/current_state/dbn_parent_source_disposition_20260705.json",
    )
    parser.add_argument(
        "--json-out",
        default="reports/data_audit/current_state/dbn_parent_source_decision_packet_20260705.json",
    )
    parser.add_argument(
        "--md-out",
        default="reports/data_audit/current_state/dbn_parent_source_decision_packet_20260705.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(args)
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(packet, md_out)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "json_out": rel(json_out),
                "md_out": rel(md_out),
                "summary": packet["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
