#!/usr/bin/env python3
"""Write a report-only prebuild plan for the broad causal rebuild root."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "data_manifest.yaml"
DEFAULT_POLICY = REPO_ROOT / REVIEW_ROOT / "broad_causal_root_policy.md"
DEFAULT_JSON_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_prebuild_plan.json"
DEFAULT_MARKDOWN_OUT = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_prebuild_plan.md"

EXPECTED_DECISION = "rebuild_new_broad_root"
EXPECTED_ROW_COUNT = 527
FUTURE_ROOT = "data/causally_gated_normalized"
FUTURE_PATTERN = f"{FUTURE_ROOT}/{{market}}/{{year}}.parquet"

ROOT_MANIFEST_FIELDS = [
    "expected_row_count",
    "produced_count",
    "deferred_count",
    "excluded_count",
    "build_command",
    "generated_at_utc",
    "config_path",
    "config_hash",
    "code_revision",
    "warnings",
]

PER_ROW_MANIFEST_FIELDS = [
    "market",
    "year",
    "input_raw_path",
    "input_raw_sha256",
    "input_raw_row_count",
    "output_causal_path",
    "output_causal_sha256",
    "output_causal_row_count",
    "timestamp_min",
    "timestamp_max",
    "schema_version",
    "status",
]

FAIL_CLOSED_STATUSES = {
    "ready_for_build": (
        "Future status only after raw/source evidence, row counts, hashes, "
        "and policy gates pass; this report-only tool does not assign it."
    ),
    "deferred_policy_review": (
        "Row is intentionally withheld from research/build approval until a "
        "separate policy decision clears it."
    ),
    "excluded_from_phase2": (
        "Row is excluded from the Phase 2 broad causal build by explicit policy."
    ),
    "action_required": (
        "Row still needs prebuild raw/source/hash/readiness validation before "
        "it can become build-ready."
    ),
}

NON_APPROVAL_TEXT = (
    "This report-only prebuild plan does not approve broader modeling, cleanup, "
    "metrics, predictions, config promotion, legacy restore, labels, features, "
    "WFA, production/live use, or model promotion."
)


@dataclass(frozen=True, order=True)
class Pair:
    market: str
    year: int

    def text(self) -> str:
        return f"{self.market}:{self.year}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
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


def format_pattern(pattern: str, pair: Pair) -> str:
    return pattern.replace("{market}", pair.market).replace("{year}", str(pair.year))


def expected_pairs(manifest: dict[str, Any]) -> list[Pair]:
    years = manifest["expected_years"]
    default_start = int(years["default_start_year"])
    end_year = int(years["end_year"])
    overrides = {
        str(market): int(start)
        for market, start in (years.get("market_start_year_overrides") or {}).items()
    }
    pairs: list[Pair] = []
    for market in [str(item) for item in manifest["expected_markets"]]:
        start_year = overrides.get(market, default_start)
        pairs.extend(Pair(market, year) for year in range(start_year, end_year + 1))
    return pairs


def validate_policy(policy_text: str) -> None:
    required = [
        EXPECTED_DECISION,
        FUTURE_ROOT,
        FUTURE_PATTERN,
        "does not approve broader modeling",
    ]
    missing = [item for item in required if item not in policy_text]
    normalized = policy_text.lower().replace("`", "")
    if "roots are evidence only" not in normalized:
        missing.append("roots are evidence only")
    if missing:
        raise ValueError(f"policy artifact missing required text: {', '.join(missing)}")


def status_for_pair(pair: Pair) -> tuple[str, str, bool]:
    if pair.year in (2025, 2026):
        return (
            "deferred_policy_review",
            "holdout_or_forward_row_non_research_until_separately_approved",
            True,
        )
    return (
        "action_required",
        "prebuild_raw_source_hash_and_policy_validation_required",
        False,
    )


def planned_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pattern = str(manifest["canonical_paths"]["raw_parquet_pattern"])
    rows: list[dict[str, Any]] = []
    for pair in expected_pairs(manifest):
        status, reason, non_research = status_for_pair(pair)
        rows.append(
            {
                "market": pair.market,
                "year": pair.year,
                "pair": pair.text(),
                "planned_input_raw_path": format_pattern(raw_pattern, pair),
                "planned_output_causal_path": format_pattern(FUTURE_PATTERN, pair),
                "non_research_until_separately_approved": non_research,
                "research_use_allowed": False,
                "prebuild_status": status,
                "status_reason": reason,
                "required_before_ready_for_build": [
                    "verify raw parquet exists without mutating data",
                    "record raw sha256 and row count",
                    "verify raw schema and timestamp bounds",
                    "resolve row-level policy exceptions or exclusions",
                    "write output causal sha256 and row count after a separately approved build",
                ],
            }
        )
    return rows


def status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in FAIL_CLOSED_STATUSES}
    for row in rows:
        status = str(row["prebuild_status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_plan(
    *,
    repo_root: Path,
    manifest_path: Path,
    policy_path: Path,
    generated_at_utc: str | None = None,
    expected_row_count: int = EXPECTED_ROW_COUNT,
) -> dict[str, Any]:
    manifest = read_yaml(manifest_path)
    policy_text = policy_path.read_text(encoding="utf-8")
    validate_policy(policy_text)
    rows = planned_rows(manifest)
    if len(rows) != expected_row_count:
        raise ValueError(
            f"configs/data_manifest.yaml expands to {len(rows)} rows, expected {expected_row_count}"
        )

    counts = status_counts(rows)
    non_research_rows = sum(
        1 for row in rows if row["non_research_until_separately_approved"]
    )
    summary = {
        "stage": "broad_causal_rebuild_prebuild_plan",
        "status": "ACTION_REQUIRED",
        "decision": EXPECTED_DECISION,
        "future_root": FUTURE_ROOT,
        "future_output_pattern": FUTURE_PATTERN,
        "expected_rows": len(rows),
        "status_counts": counts,
        "non_research_rows": non_research_rows,
        "research_use_allowed": False,
        "broader_modeling_approved": False,
        "config_promotion_approved": False,
        "legacy_restore_approved": False,
        "data_access": "did_not_read_or_write_data_files",
        "source_manifest": rel(manifest_path, repo_root),
        "source_manifest_sha256": sha256_file(manifest_path),
        "policy_artifact": rel(policy_path, repo_root),
        "policy_artifact_sha256": sha256_file(policy_path),
        "generated_at_utc": generated_at_utc or utc_now(),
        "non_approval": NON_APPROVAL_TEXT,
    }
    return {
        "summary": summary,
        "required_root_manifest_fields": ROOT_MANIFEST_FIELDS,
        "required_per_row_manifest_fields": PER_ROW_MANIFEST_FIELDS,
        "fail_closed_statuses": [
            {"status": status, "meaning": meaning}
            for status, meaning in FAIL_CLOSED_STATUSES.items()
        ],
        "validation_gates_before_build": [
            "manifest scope expands to exactly 527 rows",
            "policy artifact selects rebuild_new_broad_root",
            "raw/source/hash/readiness validation is complete for every ready row",
            "2025 holdout and 2026 forward rows remain non-research unless separately approved",
            "legacy candidate roots are not used as canonical inputs",
            "git diff --name-only -- data returns no paths before report-only steps",
        ],
        "proposed_build_command": {
            "requires_separate_approval": True,
            "command": (
                "python -m scripts.phase2_causal_base.build_causal_base_data "
                "--profile all_raw --raw-root data/raw "
                f"--output-root {FUTURE_ROOT} "
                "--reports-root reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1 "
                f"--market-year-include-list {DEFAULT_JSON_OUT.relative_to(REPO_ROOT).as_posix()}"
            ),
        },
        "rows": rows,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    counts = summary["status_counts"]
    lines = [
        "# Broad Manifest 527 Rebuild Prebuild Plan",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only prebuild validation/build design.",
        f"- Decision: `{summary['decision']}`.",
        f"- Future root: `{summary['future_root']}`.",
        f"- Future output pattern: `{summary['future_output_pattern']}`.",
        f"- `expected_rows`: {summary['expected_rows']}.",
        f"- Non-research holdout/forward rows: {summary['non_research_rows']}.",
        f"- Prebuild status counts: `{json.dumps(counts, sort_keys=True)}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- This plan does not change `configs/data_manifest.yaml`.",
        "",
        "## Required Root Manifest Fields",
        "",
        *[f"- `{field}`" for field in plan["required_root_manifest_fields"]],
        "",
        "## Required Per-Row Manifest Fields",
        "",
        *[f"- `{field}`" for field in plan["required_per_row_manifest_fields"]],
        "",
        "## Fail-Closed Statuses",
        "",
    ]
    for item in plan["fail_closed_statuses"]:
        lines.append(f"- `{item['status']}`: {item['meaning']}")
    lines.extend(
        [
            "",
            "## Validation Gates Before Build",
            "",
            *[f"- {gate}" for gate in plan["validation_gates_before_build"]],
            "",
            "## Planned Rows",
            "",
            "| pair | raw path | output path | status | non-research |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in plan["rows"]:
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['planned_input_raw_path']}` | "
            f"`{row['planned_output_causal_path']}` | "
            f"`{row['prebuild_status']}` | "
            f"{str(row['non_research_until_separately_approved']).lower()} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_plan(plan: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(plan), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    manifest_path = resolve_path(repo_root, args.manifest)
    policy_path = resolve_path(repo_root, args.policy)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        plan = build_plan(
            repo_root=repo_root,
            manifest_path=manifest_path,
            policy_path=policy_path,
        )
    except ValueError as exc:
        print(f"FAIL broad_causal_rebuild_prebuild_plan: {exc}")
        return 1
    write_plan(plan, json_out=json_out, markdown_out=markdown_out)
    summary = plan["summary"]
    print(
        "broad_causal_rebuild_prebuild_plan "
        f"status={summary['status']} "
        f"expected_rows={summary['expected_rows']} "
        f"future_root={summary['future_root']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
