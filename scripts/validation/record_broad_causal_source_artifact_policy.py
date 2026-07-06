#!/usr/bin/env python3
"""Record a report-only policy decision for blocked broad source artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_DISPOSITION = (
    REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_reference_disposition.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy.md"

EXPECTED_INPUT_STAGE = "broad_causal_source_reference_disposition"
OUTPUT_STAGE = "broad_causal_source_artifact_policy_decision"
DECISION = "continued_block_no_source_action_approved"
EXPECTED_FAILED_PAIRS = {"SR1:2020", "SR3:2020"}
EXPECTED_DISPOSITION_STATUS = "blocked_missing_current_source_artifact"

FALSE_APPROVAL_FLAGS = (
    "data_mutation_performed",
    "build_approved",
    "restore_approved",
    "repair_approved",
    "exclusion_approved",
    "broader_modeling_approved",
    "config_promotion_approved",
    "research_use_allowed",
)

NON_APPROVAL_TEXT = (
    "This report-only source artifact policy decision keeps SR1:2020 and "
    "SR3:2020 blocked. It does not approve source repair, source restore, "
    "policy exclusion, build execution, cleanup, metrics, predictions, config "
    "promotion, labels, features, WFA, broader modeling, production/live use, "
    "or model promotion."
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


def _require_equal(actual: Any, expected: Any, label: str, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label}={actual!r}, expected {expected!r}")


def validate_disposition(
    disposition: dict[str, Any],
    *,
    expected_failed_pairs: set[str] = EXPECTED_FAILED_PAIRS,
) -> list[dict[str, Any]]:
    summary = disposition.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("source-reference disposition missing summary object")
    counts = summary.get("disposition_status_counts")
    if not isinstance(counts, dict):
        raise ValueError("source-reference disposition missing summary.disposition_status_counts object")
    rows = disposition.get("rows")
    if not isinstance(rows, list):
        raise ValueError("source-reference disposition missing rows list")

    failures: list[str] = []
    _require_equal(summary.get("stage"), EXPECTED_INPUT_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), "ACTION_REQUIRED", "summary.status", failures)
    _require_equal(summary.get("failed_pair_count"), len(expected_failed_pairs), "summary.failed_pair_count", failures)
    _require_equal(set(summary.get("failed_pairs", [])), expected_failed_pairs, "summary.failed_pairs", failures)
    _require_equal(
        counts.get(EXPECTED_DISPOSITION_STATUS),
        len(expected_failed_pairs),
        f"counts.{EXPECTED_DISPOSITION_STATUS}",
        failures,
    )
    for status in (
        "blocked_current_source_hash_mismatch",
        "current_source_recovered_rerun_readiness_required",
        "invalid_unexpected_readiness_state",
    ):
        _require_equal(counts.get(status), 0, f"counts.{status}", failures)
    for flag in FALSE_APPROVAL_FLAGS:
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)
    _require_equal(summary.get("historical_evidence_only"), True, "summary.historical_evidence_only", failures)

    failed_rows = [row for row in rows if row.get("disposition_status") == EXPECTED_DISPOSITION_STATUS]
    failed_pairs = {str(row.get("pair")) for row in failed_rows}
    _require_equal(failed_pairs, expected_failed_pairs, "row.failed_pairs", failures)
    _require_equal(len(failed_rows), len(expected_failed_pairs), "row.failed_row_count", failures)

    for row in failed_rows:
        pair = str(row.get("pair"))
        _require_equal(row.get("source_file_present"), False, f"{pair}.source_file_present", failures)
        _require_equal(row.get("historical_evidence_only"), True, f"{pair}.historical_evidence_only", failures)
        source_file = str(row.get("source_file") or "")
        if not source_file:
            failures.append(f"{pair}.source_file missing")
        if not source_file.startswith("data/dbn/ohlcv_1m_parent/"):
            failures.append(f"{pair}.source_file={source_file!r} outside expected source root")

    if failures:
        raise ValueError("source-reference disposition invariant failure: " + "; ".join(failures))
    return failed_rows


def policy_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers = list(row.get("blockers") or [])
    blockers.append("no source repair, restore, exclusion, build, or modeling action approved")
    return {
        "pair": row.get("pair"),
        "market": row.get("market"),
        "year": row.get("year"),
        "source_file": row.get("source_file"),
        "planned_input_raw_path": row.get("planned_input_raw_path"),
        "raw_parquet_sha256": row.get("raw_parquet_sha256"),
        "raw_parquet_row_count": row.get("raw_parquet_row_count"),
        "timestamp_min": row.get("timestamp_min"),
        "timestamp_max": row.get("timestamp_max"),
        "input_disposition_status": row.get("disposition_status"),
        "source_file_present": row.get("source_file_present"),
        "current_source_hash_matches": row.get("current_source_hash_matches"),
        "policy_decision": DECISION,
        "policy_status": "ACTION_REQUIRED",
        "approved_action": "none",
        "blockers": blockers,
    }


def build_report(
    *,
    repo_root: Path,
    disposition_path: Path,
    generated_at_utc: str | None = None,
    expected_failed_pairs: set[str] = EXPECTED_FAILED_PAIRS,
) -> dict[str, Any]:
    disposition = read_json(disposition_path)
    rows = validate_disposition(disposition, expected_failed_pairs=expected_failed_pairs)
    policy_rows = [policy_row(row) for row in sorted(rows, key=lambda item: str(item.get("pair")))]
    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": "ACTION_REQUIRED",
            "decision": DECISION,
            "decision_meaning": (
                "SR1:2020 and SR3:2020 remain blocked because current source artifacts "
                "are absent; no source action is approved by this report."
            ),
            "input_disposition": rel(disposition_path, repo_root),
            "input_disposition_sha256": sha256_file(disposition_path),
            "generated_at_utc": generated_at_utc or utc_now(),
            "pair_count": len(policy_rows),
            "pairs": [str(row["pair"]) for row in policy_rows],
            "required_next_policy_for_source_action": (
                "A separate human-approved policy is required before source repair, "
                "source restore, exclusion/deferment execution, build execution, "
                "config promotion, or broader modeling."
            ),
            "data_access": "read_only_input_disposition_report",
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "source_action_approved": False,
            "historical_evidence_only": True,
            "non_approval": NON_APPROVAL_TEXT,
        },
        "policy_decision_definitions": {
            DECISION: (
                "Keep the two rows blocked and approve no source repair, source restore, "
                "policy exclusion, build, config promotion, or modeling action."
            )
        },
        "input_requirements": {
            "required_input_stage": EXPECTED_INPUT_STAGE,
            "required_input_status": "ACTION_REQUIRED",
            "required_failed_pairs": sorted(expected_failed_pairs),
            "required_disposition_status": EXPECTED_DISPOSITION_STATUS,
            "required_approval_flags": {flag: False for flag in FALSE_APPROVAL_FLAGS},
        },
        "rows": policy_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Broad Manifest 527 Source Artifact Policy Decision",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only policy decision for the two blocked broad source artifacts.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Pairs: `{', '.join(summary['pairs'])}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Policy Decision",
        "",
        f"- {summary['decision_meaning']}",
        f"- {summary['required_next_policy_for_source_action']}",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `build_approved`: false.",
        "- `restore_approved`: false.",
        "- `repair_approved`: false.",
        "- `exclusion_approved`: false.",
        "- `broader_modeling_approved`: false.",
        "- `config_promotion_approved`: false.",
        "- `research_use_allowed`: false.",
        "- `source_action_approved`: false.",
        "- `historical_evidence_only`: true.",
        "",
        "## Rows",
        "",
        "| pair | input disposition | policy decision | source present | approved action | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['input_disposition_status']}` | "
            f"`{row['policy_decision']}` | "
            f"{str(row['source_file_present']).lower()} | "
            f"`{row['approved_action']}` | "
            f"{blockers} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--disposition", default=str(DEFAULT_DISPOSITION))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    disposition_path = resolve_path(repo_root, args.disposition)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, disposition_path=disposition_path)
    except ValueError as exc:
        print(f"FAIL broad_causal_source_artifact_policy: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_source_artifact_policy "
        f"status={summary['status']} "
        f"decision={summary['decision']} "
        f"pair_count={summary['pair_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
