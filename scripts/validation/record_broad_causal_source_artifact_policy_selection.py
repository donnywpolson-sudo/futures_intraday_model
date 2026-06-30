#!/usr/bin/env python3
"""Record the selected continue-block policy option for broad source artifacts."""

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
DEFAULT_REQUEST = (
    REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_next_policy_request.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy_selection.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy_selection.md"

EXPECTED_INPUT_STAGE = "broad_causal_source_artifact_next_policy_request"
EXPECTED_INPUT_STATUS = "HUMAN_DECISION_REQUIRED"
CURRENT_DECISION = "continued_block_no_source_action_approved"
OUTPUT_STAGE = "broad_causal_source_artifact_policy_selection"
SELECTED_OPTION = "continue_block_no_action"
EXPECTED_PAIRS = {"SR1:2020", "SR3:2020"}
REQUESTED_DECISION_OPTIONS = [
    "approve_separate_source_repair_restore_plan",
    "approve_policy_exclusion_deferment_plan",
    SELECTED_OPTION,
]
FALSE_FLAGS = (
    "data_mutation_performed",
    "build_approved",
    "restore_approved",
    "repair_approved",
    "exclusion_approved",
    "broader_modeling_approved",
    "config_promotion_approved",
    "research_use_allowed",
    "source_action_approved",
)

NON_APPROVAL_TEXT = (
    "This report-only policy selection records continue_block_no_action. It does "
    "not approve data mutation, source repair, source restore, exclusion execution, "
    "build execution, cleanup, metrics, predictions, config promotion, labels, "
    "features, WFA, broader modeling, production/live use, or model promotion."
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


def validate_request(
    request: dict[str, Any],
    *,
    expected_pairs: set[str] = EXPECTED_PAIRS,
) -> list[dict[str, Any]]:
    summary = request.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("source artifact next-policy request missing summary object")
    rows = request.get("rows")
    if not isinstance(rows, list):
        raise ValueError("source artifact next-policy request missing rows list")

    failures: list[str] = []
    _require_equal(summary.get("stage"), EXPECTED_INPUT_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), EXPECTED_INPUT_STATUS, "summary.status", failures)
    _require_equal(summary.get("current_decision"), CURRENT_DECISION, "summary.current_decision", failures)
    _require_equal(summary.get("pair_count"), len(expected_pairs), "summary.pair_count", failures)
    _require_equal(set(summary.get("pairs", [])), expected_pairs, "summary.pairs", failures)
    _require_equal(
        summary.get("requested_decision_options"),
        REQUESTED_DECISION_OPTIONS,
        "summary.requested_decision_options",
        failures,
    )
    _require_equal(summary.get("selected_decision_option"), None, "summary.selected_decision_option", failures)
    _require_equal(summary.get("approved_action"), "none", "summary.approved_action", failures)
    for flag in FALSE_FLAGS:
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)

    row_pairs = {str(row.get("pair")) for row in rows}
    _require_equal(row_pairs, expected_pairs, "row.pairs", failures)
    _require_equal(len(rows), len(expected_pairs), "row.count", failures)
    for row in rows:
        pair = str(row.get("pair"))
        _require_equal(row.get("current_policy_decision"), CURRENT_DECISION, f"{pair}.current_policy_decision", failures)
        _require_equal(row.get("current_policy_status"), "ACTION_REQUIRED", f"{pair}.current_policy_status", failures)
        _require_equal(
            row.get("input_disposition_status"),
            "blocked_missing_current_source_artifact",
            f"{pair}.input_disposition_status",
            failures,
        )
        _require_equal(row.get("source_file_present"), False, f"{pair}.source_file_present", failures)
        _require_equal(row.get("current_approved_action"), "none", f"{pair}.current_approved_action", failures)
        _require_equal(
            row.get("requested_decision_options"),
            REQUESTED_DECISION_OPTIONS,
            f"{pair}.requested_decision_options",
            failures,
        )
        _require_equal(row.get("selected_decision_option"), None, f"{pair}.selected_decision_option", failures)
        _require_equal(row.get("approved_action"), "none", f"{pair}.approved_action", failures)
        _require_equal(row.get("decision_required"), True, f"{pair}.decision_required", failures)

    if failures:
        raise ValueError("source artifact next-policy request invariant failure: " + "; ".join(failures))
    return rows


def selection_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers = list(row.get("blockers") or [])
    blockers.append("human selected continue_block_no_action; no source/data action approved")
    return {
        "pair": row.get("pair"),
        "market": row.get("market"),
        "year": row.get("year"),
        "source_file": row.get("source_file"),
        "planned_input_raw_path": row.get("planned_input_raw_path"),
        "raw_parquet_sha256": row.get("raw_parquet_sha256"),
        "raw_parquet_row_count": row.get("raw_parquet_row_count"),
        "input_request_current_decision": row.get("current_policy_decision"),
        "input_disposition_status": row.get("input_disposition_status"),
        "source_file_present": row.get("source_file_present"),
        "selected_decision_option": SELECTED_OPTION,
        "human_decision_recorded": True,
        "approved_action": "none",
        "policy_status": "ACTION_REQUIRED",
        "blockers": blockers,
    }


def build_report(
    *,
    repo_root: Path,
    request_path: Path,
    generated_at_utc: str | None = None,
    expected_pairs: set[str] = EXPECTED_PAIRS,
) -> dict[str, Any]:
    request = read_json(request_path)
    rows = validate_request(request, expected_pairs=expected_pairs)
    selection_rows = [selection_row(row) for row in sorted(rows, key=lambda item: str(item.get("pair")))]
    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": "ACTION_REQUIRED",
            "selected_decision_option": SELECTED_OPTION,
            "human_decision_recorded": True,
            "approved_action": "none",
            "decision_meaning": (
                "SR1:2020 and SR3:2020 remain blocked; no source repair, restore, "
                "exclusion execution, build, config promotion, or modeling action is approved."
            ),
            "input_request": rel(request_path, repo_root),
            "input_request_sha256": sha256_file(request_path),
            "generated_at_utc": generated_at_utc or utc_now(),
            "pair_count": len(selection_rows),
            "pairs": [str(row["pair"]) for row in selection_rows],
            "data_access": "read_only_next_policy_request_report",
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "source_action_approved": False,
            "non_approval": NON_APPROVAL_TEXT,
        },
        "selected_decision_definition": {
            SELECTED_OPTION: (
                "Human selected continued block/no action; both rows remain action-required "
                "and no source/data/build/modeling action is approved."
            )
        },
        "input_requirements": {
            "required_input_stage": EXPECTED_INPUT_STAGE,
            "required_input_status": EXPECTED_INPUT_STATUS,
            "required_current_decision": CURRENT_DECISION,
            "required_pairs": sorted(expected_pairs),
            "required_requested_decision_options": REQUESTED_DECISION_OPTIONS,
            "required_selected_decision_option": None,
            "required_approved_action": "none",
            "required_approval_flags": {flag: False for flag in FALSE_FLAGS},
        },
        "rows": selection_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Broad Manifest 527 Source Artifact Policy Selection",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only selected policy option for the two blocked broad source artifacts.",
        f"- Status: `{summary['status']}`.",
        f"- Selected decision option: `{summary['selected_decision_option']}`.",
        f"- Human decision recorded: `{str(summary['human_decision_recorded']).lower()}`.",
        f"- Approved action: `{summary['approved_action']}`.",
        f"- Pairs: `{', '.join(summary['pairs'])}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Policy Selection",
        "",
        f"- {summary['decision_meaning']}",
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
        "",
        "## Rows",
        "",
        "| pair | selected option | human decision recorded | source present | approved action | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['selected_decision_option']}` | "
            f"{str(row['human_decision_recorded']).lower()} | "
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
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    request_path = resolve_path(repo_root, args.request)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, request_path=request_path)
    except ValueError as exc:
        print(f"FAIL broad_causal_source_artifact_policy_selection: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_source_artifact_policy_selection "
        f"status={summary['status']} "
        f"selected_decision_option={summary['selected_decision_option']} "
        f"pair_count={summary['pair_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
