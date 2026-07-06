#!/usr/bin/env python3
"""Report-only disposition plan for active-root raw-to-causal gaps."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS = (
    REPO_ROOT
    / "reports/data_audit/current_state/active_root_raw_to_causal_readiness_post_six_causal_rebuild_20260705.json"
)
DEFAULT_LEDGER = REPO_ROOT / "reports/data_audit/current_state/data_current_state_20260705T161444Z.json"
DEFAULT_RAW_ALIGNMENT = (
    REPO_ROOT / "reports/data_audit/current_state/post_sr_replacement_all_raw_dbn_alignment_20260705.json"
)
DEFAULT_SR_REPLACEMENT = (
    REPO_ROOT / "reports/data_audit/sr1_sr3_2020_parent_sidecar_raw_replacement_20260705.json"
)
DEFAULT_JSON_OUT = (
    REPO_ROOT
    / "reports/data_audit/current_state/active_root_raw_without_causal_policy_disposition_20260705.json"
)
DEFAULT_MARKDOWN_OUT = DEFAULT_JSON_OUT.with_suffix(".md")

STAGE = "active_root_raw_without_causal_policy_disposition_plan"
STATUS = "PASS_POLICY_DISPOSITION_READY_NO_EXECUTION"
REBUILD = "rebuild"
EXCLUDE = "exclude"
DEFER = "defer"
DISPOSITIONS = (REBUILD, EXCLUDE, DEFER)

EXPECTED_STALE_PAIRS = {
    "KE:2019",
    "KE:2021",
    "KE:2023",
    "KE:2024",
    "SR1:2020",
    "SR3:2020",
}
EXPECTED_RAW_WITHOUT_CAUSAL_PAIRS = {
    "6E:2025",
    "6E:2026",
    "6M:2012",
    "CL:2025",
    "CL:2026",
    "ES:2025",
    "ES:2026",
    "TN:2010",
    "TN:2011",
    "TN:2012",
    "ZN:2025",
    "ZN:2026",
}

NON_APPROVAL = (
    "This report-only disposition plan does not approve provider/network calls, "
    "data/raw or data/dbn mutation, causal parquet writes, cleanup/archive, DBN "
    "sidecar canonicalization, labels, features, WFA, predictions, modeling, "
    "commit, push, paper, or live work."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _row_by_pair(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("pair")): row for row in rows if row.get("pair")}


def _validate_scope(readiness: dict[str, Any], raw_alignment: dict[str, Any], sr_replacement: dict[str, Any]) -> None:
    summary = readiness.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("readiness report missing summary")
    failures: list[str] = []
    if summary.get("status") != "WARN":
        failures.append(f"readiness status={summary.get('status')!r}, expected 'WARN'")
    stale_count = summary.get("stale_raw_input_hash_count")
    if stale_count not in {0, len(EXPECTED_STALE_PAIRS)}:
        failures.append("unexpected stale_raw_input_hash_count")
    if summary.get("raw_without_causal_count") != len(EXPECTED_RAW_WITHOUT_CAUSAL_PAIRS):
        failures.append("unexpected raw_without_causal_count")
    if summary.get("causal_without_raw_count") != 0:
        failures.append("causal_without_raw_count must be 0")
    if summary.get("causal_without_evidence_count") != 0:
        failures.append("causal_without_evidence_count must be 0")
    if summary.get("active_causal_hash_mismatch_count") != 0:
        failures.append("active_causal_hash_mismatch_count must be 0")
    if summary.get("active_causal_row_mismatch_count") != 0:
        failures.append("active_causal_row_mismatch_count must be 0")
    if raw_alignment.get("status") != "PASS":
        failures.append(f"raw alignment status={raw_alignment.get('status')!r}, expected 'PASS'")
    if raw_alignment.get("source_hash_mismatch_count") != 0:
        failures.append("raw alignment source_hash_mismatch_count must be 0")
    if raw_alignment.get("definition_join_mismatch_count") != 0:
        failures.append("raw alignment definition_join_mismatch_count must be 0")
    if sr_replacement.get("status") != "PASS":
        failures.append(f"SR replacement status={sr_replacement.get('status')!r}, expected 'PASS'")

    stale_pairs = set(_row_by_pair(readiness.get("stale_raw_input_hash_rows") or []))
    raw_only_pairs = set(_row_by_pair(readiness.get("raw_without_causal") or []))
    if stale_count == len(EXPECTED_STALE_PAIRS) and stale_pairs != EXPECTED_STALE_PAIRS:
        failures.append(f"stale pairs mismatch: {sorted(stale_pairs)}")
    if stale_count == 0 and stale_pairs:
        failures.append(f"stale pairs should be empty after six-row rebuild: {sorted(stale_pairs)}")
    if raw_only_pairs != EXPECTED_RAW_WITHOUT_CAUSAL_PAIRS:
        failures.append(f"raw-without-causal pairs mismatch: {sorted(raw_only_pairs)}")
    if failures:
        raise ValueError("scope validation failed: " + "; ".join(failures))


def _defer_reason(pair: str, year: int) -> str:
    if year in {2025, 2026}:
        return (
            "holdout_or_forward_raw_has_no_active_causal_output; keep deferred until a separate "
            "holdout/forward causal-scope decision approves rebuild or exclusion"
        )
    if pair == "6M:2012":
        return (
            "known_roll_maturity_blocker_candidate_without_current_policy_approval; keep deferred "
            "until a separate roll-maturity disposition approves rebuild or exclusion"
        )
    if pair in {"TN:2010", "TN:2011", "TN:2012"}:
        return (
            "early_TN_raw_extra_without_current_policy_approval; keep deferred until a separate "
            "instrument-scope disposition approves rebuild or exclusion"
        )
    return (
        "raw_exists_but_approved_input_evidence_does_not_approve_causal_build_or_exclusion; "
        "keep deferred for separate policy disposition"
    )


def _candidate_notes(pair: str) -> list[str]:
    if pair == "6M:2012":
        return [
            "Known historical roll-maturity blocker candidate; this report recommends defer because neither rebuild nor exclusion is proven by the current evidence."
        ]
    if pair in {"TN:2010", "TN:2011", "TN:2012"}:
        return [
            "Known early-TN raw/DBN extra candidate; this report recommends defer because neither rebuild nor exclusion is proven by the current evidence."
        ]
    if pair.split(":", 1)[1] in {"2025", "2026"}:
        return [
            "Holdout/forward candidate; this report recommends defer until a separate holdout/forward causal-scope policy is approved."
        ]
    return []


def _market_year_from_row(row: dict[str, Any]) -> tuple[str, int]:
    market = row.get("market")
    year = row.get("year")
    if isinstance(market, str) and isinstance(year, int):
        return market, year
    pair = str(row.get("pair") or "")
    if ":" not in pair:
        raise ValueError(f"row missing market/year and pair is invalid: {pair!r}")
    market_text, year_text = pair.split(":", 1)
    return market_text, int(year_text)


def _build_rebuild_row(row: dict[str, Any]) -> dict[str, Any]:
    market, year = _market_year_from_row(row)
    return {
        "pair": row["pair"],
        "market": market,
        "year": year,
        "disposition": REBUILD,
        "reason": "active_causal_built_from_stale_raw_hash_after_accepted_raw_replacement",
        "raw_path": row["raw_path"],
        "active_causal_path": row["active_causal_path"],
        "current_raw_sha256": row["current_raw_sha256"],
        "evidence_raw_sha256": row["evidence_raw_sha256"],
        "evidence_group": row["evidence_group"],
        "requires_separate_execution_approval": True,
        "execution_approved_by_this_report": False,
        "candidate_next_action": (
            "later bounded causal-only rebuild for this pair from current data/raw into "
            "data/causally_gated_normalized, after explicit approval"
        ),
        "candidate_notes": [],
    }


def _build_defer_row(row: dict[str, Any]) -> dict[str, Any]:
    pair = str(row["pair"])
    year = int(row["year"])
    return {
        "pair": pair,
        "market": row["market"],
        "year": year,
        "disposition": DEFER,
        "reason": _defer_reason(pair, year),
        "raw_path": row["raw_path"],
        "active_causal_path": f"data/causally_gated_normalized/{row['market']}/{year}.parquet",
        "current_raw_sha256": None,
        "evidence_raw_sha256": None,
        "evidence_group": None,
        "requires_separate_execution_approval": True,
        "execution_approved_by_this_report": False,
        "candidate_next_action": (
            "keep deferred; a later report-only policy disposition may revisit rebuild or exclusion with stronger evidence"
        ),
        "candidate_notes": _candidate_notes(pair),
    }


def build_report(
    *,
    repo_root: Path,
    readiness_path: Path,
    ledger_path: Path,
    raw_alignment_path: Path,
    sr_replacement_path: Path,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    readiness = read_json(readiness_path)
    ledger = read_json(ledger_path)
    raw_alignment = read_json(raw_alignment_path)
    sr_replacement = read_json(sr_replacement_path)
    _validate_scope(readiness, raw_alignment, sr_replacement)

    stale_rows = _row_by_pair(readiness.get("stale_raw_input_hash_rows") or [])
    raw_only_rows = _row_by_pair(readiness.get("raw_without_causal") or [])
    rows = [_build_rebuild_row(stale_rows[pair]) for pair in sorted(stale_rows)]
    rows.extend(_build_defer_row(raw_only_rows[pair]) for pair in sorted(EXPECTED_RAW_WITHOUT_CAUSAL_PAIRS))

    counts = {disposition: 0 for disposition in DISPOSITIONS}
    counts.update(Counter(str(row["disposition"]) for row in rows))
    approval_template = {
        "stage": "active_root_raw_without_causal_policy_disposition_human_decision_template",
        "decision_required": True,
        "supported_approval_options": [
            "APPROVE_REPORT_ONLY_DISPOSITION_AS_PLANNING_EVIDENCE_NO_DATA_CHANGES",
            "ACCEPT_12_RAW_WITHOUT_CAUSAL_DEFER_DISPOSITION",
            "REQUEST_STRONGER_EVIDENCE_FOR_REBUILD_OR_EXCLUDE",
        ],
        "default_safe_option": "APPROVE_REPORT_ONLY_DISPOSITION_AS_PLANNING_EVIDENCE_NO_DATA_CHANGES",
        "execution_approved": False,
    }
    return {
        "summary": {
            "stage": STAGE,
            "status": STATUS,
            "generated_at_utc": generated_at_utc or utc_now(),
            "scope_row_count": len(rows),
            "rebuild_count": counts[REBUILD],
            "exclude_count": counts[EXCLUDE],
            "defer_count": counts[DEFER],
            "disposition_counts": counts,
            "input_readiness_status": readiness["summary"]["status"],
            "raw_alignment_status": raw_alignment.get("status"),
            "sr_replacement_status": sr_replacement.get("status"),
            "ledger_status": ledger.get("status"),
            "data_access": "read_existing_report_artifacts_only",
            "provider_network_calls": False,
            "data_mutation_performed": False,
            "causal_parquet_writes": False,
            "raw_without_causal_scope_pairs": sorted(EXPECTED_RAW_WITHOUT_CAUSAL_PAIRS),
            "cleanup_archive_approved": False,
            "sidecar_canonicalization_approved": False,
            "labels_features_wfa_predictions_modeling_approved": False,
            "commit_push_paper_live_approved": False,
            "execution_approved": False,
            "non_approval": NON_APPROVAL,
        },
        "input_evidence": {
            "active_root_readiness": rel(readiness_path, repo_root),
            "active_root_readiness_sha256": sha256_file(readiness_path),
            "current_state_ledger": rel(ledger_path, repo_root),
            "current_state_ledger_sha256": sha256_file(ledger_path),
            "post_sr_raw_alignment": rel(raw_alignment_path, repo_root),
            "post_sr_raw_alignment_sha256": sha256_file(raw_alignment_path),
            "sr_replacement": rel(sr_replacement_path, repo_root),
            "sr_replacement_sha256": sha256_file(sr_replacement_path),
        },
        "disposition_definitions": {
            REBUILD: "A later bounded causal-only rebuild is the selected disposition for this row; this report does not execute it.",
            EXCLUDE: "A row is explicitly excluded from causal scope by this plan. No row currently receives this disposition.",
            DEFER: "No causal build or exclusion is approved from this input evidence; keep the row out of active causal scope until stronger evidence supports rebuild or exclusion.",
        },
        "rows": rows,
        "approval_template": approval_template,
        "recommended_next_step": (
            "Accept this report-only defer disposition as current planning evidence for the 12 raw-without-causal "
            "rows, or request stronger evidence for rebuild/exclude; do not mutate data from this report alone."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Active Root Raw Without Causal Policy Disposition",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Status: `{summary['status']}`.",
        f"- Scope rows: {summary['scope_row_count']}.",
        f"- Rebuild rows: {summary['rebuild_count']}.",
        f"- Exclude rows: {summary['exclude_count']}.",
        f"- Defer rows: {summary['defer_count']}.",
        f"- Disposition counts: `{json.dumps(summary['disposition_counts'], sort_keys=True)}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `causal_parquet_writes`: false.",
        "- `execution_approved`: false.",
        "",
        "## Disposition Definitions",
        "",
    ]
    for disposition, definition in report["disposition_definitions"].items():
        lines.append(f"- `{disposition}`: {definition}")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| pair | disposition | reason | candidate next action |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['disposition']}` | "
            f"{row['reason']} | "
            f"{row['candidate_next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Approval Template",
            "",
            f"- Default safe option: `{report['approval_template']['default_safe_option']}`.",
            f"- Execution approved: `{str(report['approval_template']['execution_approved']).lower()}`.",
            "",
            "Supported options:",
            "",
        ]
    )
    lines.extend(f"- `{option}`" for option in report["approval_template"]["supported_approval_options"])
    lines.extend(["", "## Recommended Next Step", "", f"- {report['recommended_next_step']}", ""])
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--raw-alignment", default=str(DEFAULT_RAW_ALIGNMENT))
    parser.add_argument("--sr-replacement", default=str(DEFAULT_SR_REPLACEMENT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            readiness_path=resolve_path(repo_root, args.readiness),
            ledger_path=resolve_path(repo_root, args.ledger),
            raw_alignment_path=resolve_path(repo_root, args.raw_alignment),
            sr_replacement_path=resolve_path(repo_root, args.sr_replacement),
        )
    except ValueError as exc:
        print(f"FAIL active_root_causal_rebuild_disposition_plan: {exc}")
        return 1
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "active_root_raw_without_causal_policy_disposition_plan "
        f"status={summary['status']} "
        f"rebuild={summary['rebuild_count']} "
        f"exclude={summary['exclude_count']} "
        f"defer={summary['defer_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
