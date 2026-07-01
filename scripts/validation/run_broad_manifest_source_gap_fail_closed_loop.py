#!/usr/bin/env python3
"""Iterate source-gap fail-closed exclusions for broad manifest readiness."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REVIEW_ROOT = Path("reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628")
DEFAULT_OUTPUT_ROOT = Path("data/causal_base_candidates/broad_manifest_527_rebuild_v1")
DEFAULT_REPORTS_ROOT = Path("reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1")
DEFAULT_RAW_ALIGNMENT = REVIEW_ROOT / "broad_manifest_527_rebuild_all_raw_alignment.json"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pair_text(row: dict[str, Any]) -> str:
    return f"{row.get('market')}:{int(row.get('year'))}"


def _safe_pair(market: str, year: int) -> str:
    return f"{market}_{year}"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def _same_source_gap_pattern(diagnosis: dict[str, Any]) -> bool:
    return (
        diagnosis.get("source_vs_raw_call") == "raw_timestamp_set_matches_ohlcv_dbn_source_gaps"
        and diagnosis.get("timestamp_sets_match") is True
        and int(diagnosis.get("dbn_timestamps_missing_from_raw_count") or 0) == 0
        and int(diagnosis.get("raw_timestamps_missing_from_dbn_count") or 0) == 0
    )


def _exclude_pair_payload(
    *,
    include_payload: dict[str, Any],
    pair: str,
    diagnosis_json: Path,
    source_include: Path,
) -> dict[str, Any]:
    market, raw_year = pair.split(":", 1)
    year = int(raw_year)
    rows = include_payload["market_years"]
    filtered = [
        row
        for row in rows
        if not (row.get("market") == market and int(row.get("year")) == year)
    ]
    if len(filtered) != len(rows) - 1:
        raise ValueError(f"expected to exclude exactly one row for {pair}")

    new_count = len(filtered)
    payload = copy.deepcopy(include_payload)
    summary = payload["summary"]
    summary["stage"] = f"broad_manifest_527_rebuild_ready_only_include_{new_count}_source_gap_fail_closed"
    summary["status"] = f"READY_ONLY_INCLUDE_APPROVED_FOR_BUILD_{new_count}_SOURCE_GAP_FAIL_CLOSED"
    summary["approval_token"] = (
        f"APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_{new_count}_ROWS_"
        "EXCLUDING_SOURCE_GAP_FAIL_CLOSED_ROWS_ONLY"
    )
    summary["prior_approval_token"] = include_payload.get("summary", {}).get("approval_token")
    summary["approved_ready_row_count"] = new_count
    summary["latest_excluded_pair_due_to_readiness_failure"] = pair
    summary["latest_excluded_pair_disposition"] = "fail_closed_source_gap_evidence"
    summary["latest_source_vs_raw_diagnosis"] = diagnosis_json.as_posix()
    summary["source_include"] = source_include.as_posix()
    summary["generated_at_utc"] = _utc_now()
    summary["build_approved"] = True
    summary["broader_modeling_approved"] = False
    summary["config_promotion_approved"] = False
    summary["research_use_allowed"] = False
    payload["market_years"] = filtered
    fail_closed = list(payload.get("excluded_fail_closed_pairs") or [])
    if pair not in fail_closed:
        fail_closed.append(pair)
    payload["excluded_fail_closed_pairs"] = fail_closed
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include", required=True)
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--dbn-root", default="data/dbn/ohlcv_1m")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT))
    parser.add_argument("--review-root", default=str(REVIEW_ROOT))
    parser.add_argument("--summary-out", default=str(REVIEW_ROOT / "broad_manifest_source_gap_fail_closed_loop_summary.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    review_root = Path(args.review_root)
    current_include = Path(args.include)
    current_readiness = Path(args.readiness)
    history: list[dict[str, Any]] = []
    stop_reason = ""

    for iteration in range(1, max(1, args.max_iterations) + 1):
        readiness = _read_json(current_readiness)
        status = readiness.get("status")
        if status == "PASS":
            stop_reason = "readiness_pass"
            break
        blockers = readiness.get("blockers") or []
        if status != "FAIL" or len(blockers) != 1:
            stop_reason = f"unexpected_readiness_status_or_blocker_count status={status} blockers={len(blockers)}"
            break

        blocker = blockers[0]
        market = str(blocker.get("market"))
        year = int(blocker.get("year"))
        pair = f"{market}:{year}"
        reason = str(blocker.get("top_blocker_reason") or "")
        if not reason.startswith("synthetic threshold breached:"):
            stop_reason = f"non_synthetic_threshold_blocker {pair} {reason}"
            break

        diag_json = review_root / f"{_safe_pair(market, year)}_source_vs_raw_gap_diagnosis.json"
        diag_md = review_root / f"{_safe_pair(market, year)}_source_vs_raw_gap_diagnosis.md"
        diag_cmd = [
            sys.executable,
            "-m",
            "scripts.validation.diagnose_6a_2010_source_vs_raw_gaps",
            "--market",
            market,
            "--year",
            str(year),
            "--raw-root",
            args.raw_root,
            "--dbn-root",
            args.dbn_root,
            "--readiness-json",
            str(current_readiness),
            "--json-out",
            str(diag_json),
            "--md-out",
            str(diag_md),
        ]
        diag_result = _run(diag_cmd)
        if diag_result.returncode != 0 or not diag_json.exists():
            stop_reason = f"diagnostic_failed {pair} rc={diag_result.returncode}"
            break
        diagnosis = _read_json(diag_json)
        if not _same_source_gap_pattern(diagnosis):
            stop_reason = f"diagnostic_not_same_pattern {pair} call={diagnosis.get('source_vs_raw_call')}"
            break

        include_payload = _read_json(current_include)
        new_payload = _exclude_pair_payload(
            include_payload=include_payload,
            pair=pair,
            diagnosis_json=diag_json,
            source_include=current_include,
        )
        new_count = len(new_payload["market_years"])
        new_include = review_root / f"broad_manifest_527_rebuild_ready_only_include_{new_count}_source_gap_fail_closed.json"
        _write_json(new_include, new_payload)

        new_readiness = review_root / f"broad_manifest_527_rebuild_phase2_readiness_{new_count}_source_gap_fail_closed.json"
        new_readiness_md = review_root / f"broad_manifest_527_rebuild_phase2_readiness_{new_count}_source_gap_fail_closed.md"
        preflight_cmd = [
            sys.executable,
            "-m",
            "scripts.phase2_causal_base.build_causal_base_data",
            "--profile",
            "all_raw",
            "--raw-root",
            args.raw_root,
            "--output-root",
            args.output_root,
            "--reports-root",
            args.reports_root,
            "--raw-alignment-report",
            args.raw_alignment_report,
            "--market-year-include-list",
            str(new_include),
            "--readiness-only",
            "--readiness-json-out",
            str(new_readiness),
            "--readiness-md-out",
            str(new_readiness_md),
        ]
        preflight_result = _run(preflight_cmd)
        if not new_readiness.exists():
            stop_reason = f"preflight_did_not_write_report {pair} rc={preflight_result.returncode}"
            break

        next_readiness = _read_json(new_readiness)
        history.append(
            {
                "iteration": iteration,
                "excluded_pair": pair,
                "source_vs_raw_call": diagnosis.get("source_vs_raw_call"),
                "raw_rows": diagnosis.get("raw_row_count"),
                "dbn_rows": diagnosis.get("dbn_row_count"),
                "dbn_missing_from_raw": diagnosis.get("dbn_timestamps_missing_from_raw_count"),
                "raw_missing_from_dbn": diagnosis.get("raw_timestamps_missing_from_dbn_count"),
                "new_include": new_include.as_posix(),
                "new_include_count": new_count,
                "new_readiness": new_readiness.as_posix(),
                "new_readiness_status": next_readiness.get("status"),
                "next_blocker": _pair_text((next_readiness.get("blockers") or [{}])[0])
                if next_readiness.get("blockers")
                else None,
                "next_reason": (next_readiness.get("blockers") or [{}])[0].get("top_blocker_reason")
                if next_readiness.get("blockers")
                else None,
                "preflight_returncode": preflight_result.returncode,
            }
        )
        current_include = new_include
        current_readiness = new_readiness
        if next_readiness.get("status") == "PASS":
            stop_reason = "readiness_pass"
            break

    if not stop_reason:
        stop_reason = f"max_iterations_reached_{args.max_iterations}"

    summary = {
        "stage": "broad_manifest_source_gap_fail_closed_loop",
        "status": "PASS_READY_FOR_BUILD_GATE" if stop_reason == "readiness_pass" else "STOPPED",
        "stop_reason": stop_reason,
        "iterations": len(history),
        "history": history,
        "current_include": current_include.as_posix(),
        "current_readiness": current_readiness.as_posix(),
        "build_executed": False,
        "provider_or_network_call": False,
        "data_raw_mutated": False,
        "config_mutated": False,
    }
    _write_json(Path(args.summary_out), summary)
    print(json.dumps(summary, indent=2))
    return 0 if stop_reason == "readiness_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
