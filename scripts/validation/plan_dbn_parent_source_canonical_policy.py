"""Report-only canonical-source policy for unresolved DBN parent rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PACKET_STATUS = "PASS_PARENT_SOURCE_DECISION_PACKET_READY_NO_EXECUTION"
POLICY_STATUS = "PASS_DBN_PARENT_SOURCE_CANONICAL_POLICY_READY_NO_EXECUTION"
EXPECTED_PACKET_ROWS = 112
EXPECTED_STATUS_EQUALITY_ROWS = {
    ("HE", 2013),
    ("KE", 2014),
    ("LE", 2010),
    ("LE", 2011),
    ("LE", 2012),
    ("LE", 2013),
}
CANONICAL_PHASE2_SCHEMA_ROOTS = {
    "definition": "data/dbn/definition/",
    "ohlcv_1m": "data/dbn/ohlcv_1m/",
    "statistics": "data/dbn/statistics/",
    "status": "data/dbn/status/",
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


def split_nonempty(values: pd.Series) -> set[str]:
    return {str(value) for value in values.dropna().unique() if str(value)}


def read_source_columns(path: Path) -> pd.DataFrame:
    columns = list(pd.read_parquet(path).columns)
    source_columns = [
        column
        for column in columns
        if column.endswith("_source_file")
        or column.endswith("_source_sha256")
        or column in {"source_file", "source_sha256"}
    ]
    return pd.read_parquet(path, columns=source_columns)


def unique_causal_raw_link(causal_path: Path) -> list[dict[str, str]]:
    frame = pd.read_parquet(causal_path, columns=["source_path", "source_file_hash"])
    return (
        frame[["source_path", "source_file_hash"]]
        .drop_duplicates()
        .astype(str)
        .sort_values(["source_path", "source_file_hash"])
        .to_dict("records")
    )


def frame_digest(frame: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(json.dumps([str(column) for column in frame.columns]).encode("utf-8"))
    h.update(b"\0")
    h.update(json.dumps([str(dtype) for dtype in frame.dtypes]).encode("utf-8"))
    h.update(b"\0")
    hashes = pd.util.hash_pandas_object(frame, index=True).values
    h.update(hashes.tobytes())
    return h.hexdigest()


def decoded_dbn_frame(path: Path) -> pd.DataFrame:
    import databento as db  # type: ignore[import-not-found]

    frame = db.DBNStore.from_file(path).to_df(pretty_ts=False, map_symbols=False)
    if isinstance(frame, list):
        frame = pd.concat(frame, ignore_index=False)
    frame = frame.reset_index(drop=False)
    frame.columns = [str(column) for column in frame.columns]
    return frame


def compare_decoded_dbn(parent_path: Path, canonical_path: Path) -> dict[str, Any]:
    parent = decoded_dbn_frame(parent_path)
    canonical = decoded_dbn_frame(canonical_path)
    columns_match = list(parent.columns) == list(canonical.columns)
    dtypes_match = [str(dtype) for dtype in parent.dtypes] == [
        str(dtype) for dtype in canonical.dtypes
    ]
    row_count_match = len(parent) == len(canonical)
    row_order_match = columns_match and dtypes_match and row_count_match and parent.equals(canonical)
    if columns_match:
        sort_columns = list(parent.columns)
        parent_for_compare = parent.sort_values(sort_columns, kind="mergesort").reset_index(
            drop=True
        )
        canonical_for_compare = canonical.sort_values(
            sort_columns, kind="mergesort"
        ).reset_index(drop=True)
    else:
        parent_for_compare = parent
        canonical_for_compare = canonical
    records_match = (
        columns_match
        and dtypes_match
        and row_count_match
        and parent_for_compare.equals(canonical_for_compare)
    )
    return {
        "parent_decoded_rows": len(parent),
        "canonical_decoded_rows": len(canonical),
        "columns_match": columns_match,
        "dtypes_match": dtypes_match,
        "row_count_match": row_count_match,
        "row_order_match": row_order_match,
        "decoded_records_match": records_match,
        "comparison_mode": "sorted_full_record_set",
        "parent_decoded_digest": frame_digest(parent_for_compare),
        "canonical_decoded_digest": frame_digest(canonical_for_compare),
    }


def canonical_prefix(paths: set[str], schema_key: str) -> bool:
    prefix = CANONICAL_PHASE2_SCHEMA_ROOTS[schema_key]
    return bool(paths) and all(path.startswith(prefix) for path in paths)


def build_phase2_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pair_keys = sorted({(row["market"], int(row["year"])) for row in rows})
    row_by_key = {(row["market"], int(row["year"]), row["schema_key"]): row for row in rows}
    pair_rows = []
    counters: Counter[str] = Counter()

    for market, year in pair_keys:
        raw_path = Path("data/raw") / market / f"{year}.parquet"
        causal_path = Path("data/causally_gated_normalized") / market / f"{year}.parquet"
        raw_hash = file_sha256(raw_path)
        causal_link = unique_causal_raw_link(causal_path)
        causal_links_current_raw = causal_link == [
            {"source_path": rel(raw_path), "source_file_hash": raw_hash}
        ]
        counters["causal_links_current_raw" if causal_links_current_raw else "causal_link_other"] += 1

        raw = read_source_columns(raw_path)
        ohlcv_paths = split_nonempty(raw["source_file"])
        definition_paths = split_nonempty(raw.get("definition_source_file", pd.Series(dtype=object)))
        status_paths = split_nonempty(raw.get("status_source_file", pd.Series(dtype=object)))
        statistics_paths: set[str] = set()
        for column in raw.columns:
            if column.startswith("stat_") and column.endswith("_source_file"):
                statistics_paths.update(split_nonempty(raw[column]))

        ohlcv_row = row_by_key.get((market, year, "ohlcv_1m"))
        if ohlcv_row and ohlcv_paths == {ohlcv_row["canonical_target_path"]}:
            ohlcv_classification = "canonical"
        elif ohlcv_row and ohlcv_paths == {ohlcv_row["parent_path"]}:
            ohlcv_classification = "parent"
        elif canonical_prefix(ohlcv_paths, "ohlcv_1m"):
            ohlcv_classification = "canonical_prefix"
        else:
            ohlcv_classification = "other_or_empty"
        counters[f"ohlcv_1m_{ohlcv_classification}"] += 1

        definition_classification = (
            "canonical" if canonical_prefix(definition_paths, "definition") else "other_or_empty"
        )
        counters[f"definition_{definition_classification}"] += 1

        statistics_row = row_by_key.get((market, year, "statistics"))
        if statistics_row and statistics_paths == {statistics_row["canonical_target_path"]}:
            statistics_classification = "canonical"
        elif statistics_row and statistics_paths == {statistics_row["parent_path"]}:
            statistics_classification = "parent"
        elif canonical_prefix(statistics_paths, "statistics"):
            statistics_classification = "canonical_prefix_no_parent_row"
        elif not statistics_paths:
            statistics_classification = "empty"
        else:
            statistics_classification = "other"
        counters[f"statistics_{statistics_classification}"] += 1

        status_row = row_by_key.get((market, year, "status"))
        if status_row and status_paths == {status_row["canonical_target_path"]}:
            status_classification = "canonical"
        elif status_row and status_paths == {status_row["parent_path"]}:
            status_classification = "parent"
        elif not status_paths:
            status_classification = "empty_parent_comparable" if status_row else "empty_no_parent_row"
        elif canonical_prefix(status_paths, "status"):
            status_classification = "canonical_prefix_no_parent_row"
        else:
            status_classification = "other"
        counters[f"status_{status_classification}"] += 1

        pair_rows.append(
            {
                "market": market,
                "year": year,
                "raw_path": rel(raw_path),
                "raw_sha256": raw_hash,
                "causal_path": rel(causal_path),
                "causal_links_current_raw": causal_links_current_raw,
                "ohlcv_source_classification": ohlcv_classification,
                "ohlcv_source_paths": sorted(ohlcv_paths),
                "definition_source_classification": definition_classification,
                "definition_source_paths": sorted(definition_paths),
                "statistics_source_classification": statistics_classification,
                "statistics_source_paths": sorted(statistics_paths),
                "status_source_classification": status_classification,
                "status_source_paths": sorted(status_paths),
            }
        )

    return {
        "unique_market_year_count": len(pair_keys),
        "summary_counts": dict(sorted(counters.items())),
        "pairs": pair_rows,
    }


def build_policy(args: argparse.Namespace) -> dict[str, Any]:
    packet = load_json(Path(args.decision_packet_json))
    if packet.get("status") != PACKET_STATUS:
        raise ValueError(f"decision packet status must be {PACKET_STATUS}")

    rows = list(packet.get("rows", []))
    if len(rows) != EXPECTED_PACKET_ROWS:
        raise ValueError(f"expected {EXPECTED_PACKET_ROWS} packet rows")

    phase2_trace = build_phase2_trace(rows)
    policy_rows = []
    equality_rows = []

    for row in rows:
        parent_path = Path(row["parent_path"])
        canonical_path = Path(row["canonical_target_path"])
        if file_sha256(parent_path) != row["parent_sha256"]:
            raise ValueError(f"parent hash mismatch: {rel(parent_path)}")
        if canonical_path.is_file() and file_sha256(canonical_path) != row["canonical_target_sha256"]:
            raise ValueError(f"canonical hash mismatch: {rel(canonical_path)}")

        key = (row["market"], int(row["year"]))
        is_status_equality_row = (
            row["schema_key"] == "status"
            and row["source_decision_classification"] == "both_exist_parent_and_canonical_differ"
        )
        if is_status_equality_row:
            if key not in EXPECTED_STATUS_EQUALITY_ROWS:
                raise ValueError(f"unexpected status equality row: {key}")
            comparison = compare_decoded_dbn(parent_path, canonical_path)
            equality_rows.append({**row, "decoded_comparison": comparison})
            decision = "archive_candidate_after_status_decoded_equality_proof"
            reason = (
                "status lineage is empty in raw parquet, but parent and canonical "
                "status DBNs decode to identical records"
            )
        else:
            comparison = {}
            decision = "archive_candidate_canonical_phase2_lineage"
            reason = (
                "Phase 2 lineage uses canonical DBN/raw sources; parent DBN is not "
                "active downstream provenance"
            )

        policy_rows.append(
            {
                "market": row["market"],
                "year": row["year"],
                "schema_key": row["schema_key"],
                "parent_path": row["parent_path"],
                "parent_sha256": row["parent_sha256"],
                "canonical_target_path": row["canonical_target_path"],
                "canonical_target_sha256": row["canonical_target_sha256"],
                "source_decision_classification": row["source_decision_classification"],
                "policy_decision": decision,
                "policy_reason": reason,
                "decoded_comparison": comparison,
            }
        )

    equality_keys = {(row["market"], int(row["year"])) for row in equality_rows}
    equality_pass = (
        equality_keys == EXPECTED_STATUS_EQUALITY_ROWS
        and all(row["decoded_comparison"]["decoded_records_match"] for row in equality_rows)
    )
    policy_counts = Counter(row["policy_decision"] for row in policy_rows)
    phase2_counts = phase2_trace["summary_counts"]
    phase2_pass = (
        phase2_trace["unique_market_year_count"] == 38
        and phase2_counts.get("causal_links_current_raw") == 38
        and phase2_counts.get("ohlcv_1m_canonical") == 38
        and phase2_counts.get("definition_canonical") == 38
        and phase2_counts.get("statistics_canonical") == 37
        and phase2_counts.get("statistics_canonical_prefix_no_parent_row") == 1
        and phase2_counts.get("status_canonical") == 31
        and phase2_counts.get("status_empty_parent_comparable") == 6
        and phase2_counts.get("status_empty_no_parent_row") == 1
    )
    policy_pass = (
        dict(policy_counts)
        == {
            "archive_candidate_canonical_phase2_lineage": 106,
            "archive_candidate_after_status_decoded_equality_proof": 6,
        }
        and equality_pass
        and phase2_pass
    )

    return {
        "stage": "dbn_parent_source_canonical_policy",
        "status": POLICY_STATUS if policy_pass else "WARN_DBN_PARENT_SOURCE_CANONICAL_POLICY_REVIEW_REQUIRED",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "decision_packet_json": args.decision_packet_json,
        "scope": "report-only canonical Phase 2 DBN-source policy for 112 unresolved parent-source rows",
        "non_approval": {
            "file_moves": False,
            "file_deletes": False,
            "provider_network_calls": False,
            "sidecar_canonicalization": False,
            "parent_source_promotion": False,
            "raw_causal_label_feature_wfa_prediction_modeling": False,
            "commit_push_paper_live": False,
        },
        "policy_statement": (
            "Use canonical data/dbn/{ohlcv_1m,definition,statistics,status} as the "
            "trusted Phase 2 DBN source set for the scoped HE/KE/LE market-years. "
            "The unresolved _parent DBNs are archive candidates only; this report "
            "approves no moves, deletes, or promotions."
        ),
        "summary": {
            "packet_row_count": len(policy_rows),
            "unique_market_year_count": phase2_trace["unique_market_year_count"],
            "policy_decision_counts": dict(sorted(policy_counts.items())),
            "status_equality_row_count": len(equality_rows),
            "status_equality_expected_rows": [
                {"market": market, "year": year}
                for market, year in sorted(EXPECTED_STATUS_EQUALITY_ROWS)
            ],
            "status_equality_all_decoded_records_match": equality_pass,
            "phase2_trace_counts": phase2_counts,
            "approved_file_moves": 0,
            "approved_file_deletes": 0,
            "approved_data_mutations": 0,
        },
        "phase2_trace": phase2_trace,
        "status_equality_rows": equality_rows,
        "rows": policy_rows,
        "recommended_next_step": (
            "If cleanup execution is desired, approve a separate bounded move-only "
            "archive plan for the exact 112 parent-source rows classified here as "
            "archive candidates; do not delete, promote, canonicalize, rebuild, "
            "commit, push, paper, or live work."
        ),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# DBN Parent-Source Canonical Policy",
        "",
        f"- Status: `{report['status']}`.",
        f"- Decision packet: `{report['decision_packet_json']}`.",
        "- Approved moves/deletes/data mutations: `0`.",
        "- Provider calls, sidecar canonicalization, parent-source promotion, downstream rebuilds, commits, pushes, paper, and live work: `none`.",
        "",
        "## Policy",
        "",
        report["policy_statement"],
        "",
        "## Summary",
        "",
        f"- Packet rows: `{report['summary']['packet_row_count']}`.",
        f"- Unique market-years: `{report['summary']['unique_market_year_count']}`.",
        f"- Policy decision counts: `{json.dumps(report['summary']['policy_decision_counts'], sort_keys=True)}`.",
        f"- Status equality rows: `{report['summary']['status_equality_row_count']}`.",
        f"- Status equality decoded records match: `{report['summary']['status_equality_all_decoded_records_match']}`.",
        f"- Phase 2 trace counts: `{json.dumps(report['summary']['phase2_trace_counts'], sort_keys=True)}`.",
        "",
        "## Six Status Equality Rows",
        "",
        "| Market | Year | Parent rows | Canonical rows | Decoded match | Parent path | Canonical path |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for row in report["status_equality_rows"]:
        comparison = row["decoded_comparison"]
        lines.append(
            f"| `{row['market']}` | `{row['year']}` | {comparison['parent_decoded_rows']} | {comparison['canonical_decoded_rows']} | `{comparison['decoded_records_match']}` | `{row['parent_path']}` | `{row['canonical_target_path']}` |"
        )

    lines.extend(
        [
            "",
            "## Phase 2 Source Trace",
            "",
            "| Market | Year | Causal links current raw | OHLCV | Definition | Statistics | Status |",
            "|---|---:|---|---|---|---|---|",
        ]
    )
    for row in report["phase2_trace"]["pairs"]:
        lines.append(
            f"| `{row['market']}` | `{row['year']}` | `{row['causal_links_current_raw']}` | `{row['ohlcv_source_classification']}` | `{row['definition_source_classification']}` | `{row['statistics_source_classification']}` | `{row['status_source_classification']}` |"
        )

    lines.extend(
        [
            "",
            "## Parent Row Policy",
            "",
            "| Policy decision | Market | Year | Schema | Parent path |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            f"| `{row['policy_decision']}` | `{row['market']}` | `{row['year']}` | `{row['schema_key']}` | `{row['parent_path']}` |"
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
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decision-packet-json",
        default="reports/data_audit/current_state/dbn_parent_source_decision_packet_20260705.json",
    )
    parser.add_argument(
        "--json-out",
        default="reports/data_audit/current_state/dbn_parent_source_canonical_policy_20260705.json",
    )
    parser.add_argument(
        "--md-out",
        default="reports/data_audit/current_state/dbn_parent_source_canonical_policy_20260705.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_policy(args)
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
                "summary": report["summary"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == POLICY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
