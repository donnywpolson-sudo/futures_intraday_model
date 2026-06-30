#!/usr/bin/env python3
"""Request the next human policy decision for blocked broad source artifacts."""

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
DEFAULT_POLICY = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_policy.json"
DEFAULT_JSON_OUT = (
    REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_next_policy_request.json"
)
DEFAULT_MARKDOWN_OUT = (
    REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_source_artifact_next_policy_request.md"
)

EXPECTED_INPUT_STAGE = "broad_causal_source_artifact_policy_decision"
EXPECTED_CURRENT_DECISION = "continued_block_no_source_action_approved"
OUTPUT_STAGE = "broad_causal_source_artifact_next_policy_request"
OUTPUT_STATUS = "HUMAN_DECISION_REQUIRED"
EXPECTED_PAIRS = {"SR1:2020", "SR3:2020"}
REQUESTED_DECISION_OPTIONS = [
    "approve_separate_source_repair_restore_plan",
    "approve_policy_exclusion_deferment_plan",
    "continue_block_no_action",
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
    "This report-only next-policy request does not select a decision option and "
    "does not approve data mutation, source repair, source restore, exclusion "
    "execution, build execution, cleanup, metrics, predictions, config promotion, "
    "labels, features, WFA, broader modeling, production/live use, or model promotion."
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


def validate_policy(
    policy: dict[str, Any],
    *,
    expected_pairs: set[str] = EXPECTED_PAIRS,
) -> list[dict[str, Any]]:
    summary = policy.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("source artifact policy missing summary object")
    rows = policy.get("rows")
    if not isinstance(rows, list):
        raise ValueError("source artifact policy missing rows list")

    failures: list[str] = []
    _require_equal(summary.get("stage"), EXPECTED_INPUT_STAGE, "summary.stage", failures)
    _require_equal(summary.get("status"), "ACTION_REQUIRED", "summary.status", failures)
    _require_equal(summary.get("decision"), EXPECTED_CURRENT_DECISION, "summary.decision", failures)
    _require_equal(summary.get("pair_count"), len(expected_pairs), "summary.pair_count", failures)
    _require_equal(set(summary.get("pairs", [])), expected_pairs, "summary.pairs", failures)
    for flag in FALSE_FLAGS:
        _require_equal(summary.get(flag), False, f"summary.{flag}", failures)

    row_pairs = {str(row.get("pair")) for row in rows}
    _require_equal(row_pairs, expected_pairs, "row.pairs", failures)
    _require_equal(len(rows), len(expected_pairs), "row.count", failures)
    for row in rows:
        pair = str(row.get("pair"))
        _require_equal(row.get("policy_decision"), EXPECTED_CURRENT_DECISION, f"{pair}.policy_decision", failures)
        _require_equal(row.get("policy_status"), "ACTION_REQUIRED", f"{pair}.policy_status", failures)
        _require_equal(row.get("approved_action"), "none", f"{pair}.approved_action", failures)
        _require_equal(row.get("source_file_present"), False, f"{pair}.source_file_present", failures)
        _require_equal(
            row.get("input_disposition_status"),
            "blocked_missing_current_source_artifact",
            f"{pair}.input_disposition_status",
            failures,
        )

    if failures:
        raise ValueError("source artifact policy invariant failure: " + "; ".join(failures))
    return rows


def request_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pair": row.get("pair"),
        "market": row.get("market"),
        "year": row.get("year"),
        "source_file": row.get("source_file"),
        "planned_input_raw_path": row.get("planned_input_raw_path"),
        "raw_parquet_sha256": row.get("raw_parquet_sha256"),
        "raw_parquet_row_count": row.get("raw_parquet_row_count"),
        "current_policy_decision": row.get("policy_decision"),
        "current_policy_status": row.get("policy_status"),
        "input_disposition_status": row.get("input_disposition_status"),
        "source_file_present": row.get("source_file_present"),
        "current_approved_action": row.get("approved_action"),
        "requested_decision_options": REQUESTED_DECISION_OPTIONS,
        "selected_decision_option": None,
        "approved_action": "none",
        "decision_required": True,
        "blockers": list(row.get("blockers") or []),
    }


def build_report(
    *,
    repo_root: Path,
    policy_path: Path,
    generated_at_utc: str | None = None,
    expected_pairs: set[str] = EXPECTED_PAIRS,
) -> dict[str, Any]:
    policy = read_json(policy_path)
    rows = validate_policy(policy, expected_pairs=expected_pairs)
    request_rows = [request_row(row) for row in sorted(rows, key=lambda item: str(item.get("pair")))]
    return {
        "summary": {
            "stage": OUTPUT_STAGE,
            "status": OUTPUT_STATUS,
            "current_decision": EXPECTED_CURRENT_DECISION,
            "input_policy": rel(policy_path, repo_root),
            "input_policy_sha256": sha256_file(policy_path),
            "generated_at_utc": generated_at_utc or utc_now(),
            "pair_count": len(request_rows),
            "pairs": [str(row["pair"]) for row in request_rows],
            "requested_decision_options": REQUESTED_DECISION_OPTIONS,
            "selected_decision_option": None,
            "approved_action": "none",
            "decision_request_reason": (
                "Current policy keeps SR1:2020 and SR3:2020 blocked with no source action approved; "
                "a human policy decision is required before any source repair/restore plan, "
                "policy exclusion/deferment plan, or continued block update."
            ),
            "data_access": "read_only_current_policy_report",
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
        "decision_option_definitions": {
            "approve_separate_source_repair_restore_plan": (
                "Human selects a future report-only planning path for source repair or restore; "
                "this request does not execute or approve that action."
            ),
            "approve_policy_exclusion_deferment_plan": (
                "Human selects a future report-only planning path for exclusion or deferment; "
                "this request does not execute or approve that action."
            ),
            "continue_block_no_action": (
                "Human confirms both rows remain blocked with no source action, build, "
                "config promotion, or modeling approval."
            ),
        },
        "input_requirements": {
            "required_input_stage": EXPECTED_INPUT_STAGE,
            "required_input_status": "ACTION_REQUIRED",
            "required_current_decision": EXPECTED_CURRENT_DECISION,
            "required_pairs": sorted(expected_pairs),
            "required_row_approved_action": "none",
            "required_approval_flags": {flag: False for flag in FALSE_FLAGS},
        },
        "rows": request_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Broad Manifest 527 Source Artifact Next Policy Request",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only request for the next human policy decision.",
        f"- Status: `{summary['status']}`.",
        f"- Current decision: `{summary['current_decision']}`.",
        f"- Selected decision option: `{summary['selected_decision_option']}`.",
        f"- Approved action: `{summary['approved_action']}`.",
        f"- Pairs: `{', '.join(summary['pairs'])}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Decision Options",
        "",
    ]
    for option, meaning in report["decision_option_definitions"].items():
        lines.append(f"- `{option}`: {meaning}")
    lines.extend(
        [
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
            "| pair | current decision | requested options | selected option | approved action | blockers |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["rows"]:
        blockers = "; ".join(str(item) for item in row.get("blockers", []))
        options = ", ".join(f"`{option}`" for option in row["requested_decision_options"])
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['current_policy_decision']}` | "
            f"{options} | "
            f"`{row['selected_decision_option']}` | "
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
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    policy_path = resolve_path(repo_root, args.policy)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, policy_path=policy_path)
    except ValueError as exc:
        print(f"FAIL broad_causal_source_artifact_next_policy_request: {exc}")
        return 1
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "broad_causal_source_artifact_next_policy_request "
        f"status={summary['status']} "
        f"current_decision={summary['current_decision']} "
        f"pair_count={summary['pair_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
