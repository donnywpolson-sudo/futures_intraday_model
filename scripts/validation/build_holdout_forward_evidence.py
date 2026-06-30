#!/usr/bin/env python3
"""Report-only evidence gate for 2025 holdout and 2026 forward rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from scripts.phase2_causal_base.build_causal_base_data import process_file
from scripts.validation import validate_broad_causal_raw_source_readiness as raw_readiness


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALPHA_CONFIG = REPO_ROOT / "configs/alpha_tiered.yaml"
DEFAULT_INPUT_ROOT = REPO_ROOT / "data/raw"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data/causal_base_candidates/broad_manifest_527_rebuild_v1"
DEFAULT_REPORT_ROOT = (
    REPO_ROOT / "reports/data_audit/holdout_forward_evidence/broad_manifest_527_rebuild_v1"
)
DEFAULT_JSON_OUT = DEFAULT_REPORT_ROOT / "holdout_forward_evidence.json"
DEFAULT_MARKDOWN_OUT = DEFAULT_REPORT_ROOT / "holdout_forward_evidence.md"

HOLDOUT_PROFILE = "tier_3_holdout"
FORWARD_PROFILE = "tier_3_forward"
EXPECTED_MARKET_COUNT = 33
EXPECTED_ROW_COUNT = 66

LOCKED_HOLDOUT_CANDIDATE = "locked_holdout_candidate"
FORWARD_CANDIDATE = "forward_candidate"
BLOCKED = "blocked"
NOT_CHECKED = "not_checked"
BUCKETS = [LOCKED_HOLDOUT_CANDIDATE, FORWARD_CANDIDATE, BLOCKED, NOT_CHECKED]

NON_APPROVAL = (
    "This report-only holdout/forward evidence gate does not approve build output, "
    "research use, modeling, WFA, predictions, metrics, config promotion, staging, "
    "commits, production/live use, or broader promotion."
)

RawInspector = Callable[..., dict[str, Any]]
Phase2Inspector = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _profile(config: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("alpha config missing profiles mapping")
    profile = profiles.get(name)
    if not isinstance(profile, dict):
        raise ValueError(f"profile missing or invalid: {name}")
    return profile


def _validate_profile(
    profile: dict[str, Any],
    *,
    profile_name: str,
    expected_year: int,
) -> list[str]:
    years = [int(year) for year in profile.get("years", [])]
    markets = [str(market) for market in profile.get("markets", [])]
    failures: list[str] = []
    if years != [expected_year]:
        failures.append(f"{profile_name} years={years!r}, expected [{expected_year}]")
    if not bool(profile.get("forbid_research_use", False)):
        failures.append(f"{profile_name} missing forbid_research_use=true")
    if len(markets) != EXPECTED_MARKET_COUNT:
        failures.append(
            f"{profile_name} market_count={len(markets)!r}, expected {EXPECTED_MARKET_COUNT!r}"
        )
    duplicates = sorted(market for market, count in Counter(markets).items() if count != 1)
    if duplicates:
        failures.append(f"{profile_name} duplicate markets: {duplicates}")
    if failures:
        raise ValueError("; ".join(failures))
    return markets


def validate_scope_rows(rows: list[dict[str, Any]], *, max_rows: int) -> None:
    pairs = [str(row["pair"]) for row in rows]
    duplicate_pairs = sorted(pair for pair, count in Counter(pairs).items() if count != 1)
    forbidden_pairs = sorted(pair for pair in pairs if pair == "6M:2012")
    research_year_pairs = sorted(
        str(row["pair"]) for row in rows if int(row["year"]) <= 2024
    )
    failures: list[str] = []
    if len(rows) != max_rows:
        failures.append(f"scope row count={len(rows)!r}, expected {max_rows!r}")
    if duplicate_pairs:
        failures.append(f"duplicate market-years: {duplicate_pairs}")
    if forbidden_pairs:
        failures.append(f"forbidden market-years present: {forbidden_pairs}")
    if research_year_pairs:
        failures.append(f"research-year rows are not allowed in this gate: {research_year_pairs}")
    if failures:
        raise ValueError("; ".join(failures))


def collect_scope_rows(
    *,
    alpha_config: dict[str, Any],
    input_root: Path,
    output_root: Path,
    holdout_profile: str = HOLDOUT_PROFILE,
    forward_profile: str = FORWARD_PROFILE,
    max_rows: int = EXPECTED_ROW_COUNT,
) -> list[dict[str, Any]]:
    scope: list[dict[str, Any]] = []
    for profile_name, expected_year, bucket in (
        (holdout_profile, 2025, LOCKED_HOLDOUT_CANDIDATE),
        (forward_profile, 2026, FORWARD_CANDIDATE),
    ):
        profile = _profile(alpha_config, profile_name)
        markets = _validate_profile(
            profile,
            profile_name=profile_name,
            expected_year=expected_year,
        )
        for market in markets:
            pair = f"{market}:{expected_year}"
            scope.append(
                {
                    "profile": profile_name,
                    "market": market,
                    "year": expected_year,
                    "pair": pair,
                    "bucket_if_pass": bucket,
                    "planned_input_raw_path": (input_root / market / f"{expected_year}.parquet").as_posix(),
                    "planned_output_causal_path": (
                        output_root / market / f"{expected_year}.parquet"
                    ).as_posix(),
                    "prebuild_status": "deferred_policy_review",
                }
            )
    validate_scope_rows(scope, max_rows=max_rows)
    return scope


def existing_holdout_forward_outputs(output_root: Path) -> list[Path]:
    if not output_root.exists():
        return []
    paths = [*output_root.glob("*/2025.parquet"), *output_root.glob("*/2026.parquet")]
    return sorted(path for path in paths if path.exists())


def _phase2_check(
    *,
    repo_root: Path,
    row: dict[str, Any],
    profile: str,
    output_root: Path,
) -> dict[str, Any]:
    raw_path = resolve_path(repo_root, str(row["planned_input_raw_path"]))
    output_path = output_root / str(row["market"]) / f"{int(row['year'])}.parquet"
    result = process_file(raw_path, output_path, profile=profile, write_output=False)
    return {
        "phase2_status": result.status,
        "raw_rows": result.raw_rows,
        "output_rows": result.output_rows,
        "warnings": list(result.warnings),
        "failures": list(result.failures),
        "diagnostic_warnings": list(result.diagnostic_warnings),
        "roll_maturity_backstep_count": result.roll_maturity_backstep_count,
        "synthetic_rows_pct": result.synthetic_rows_pct,
        "roll_window_rows_pct": result.roll_window_rows_pct,
    }


def build_evidence(
    *,
    repo_root: Path,
    alpha_config_path: Path,
    input_root: Path,
    output_root: Path,
    generated_at_utc: str | None = None,
    holdout_profile: str = HOLDOUT_PROFILE,
    forward_profile: str = FORWARD_PROFILE,
    phase2_profile: str = "all_raw",
    max_rows: int = EXPECTED_ROW_COUNT,
    raw_inspector: RawInspector = raw_readiness.validate_action_required_row,
    phase2_inspector: Phase2Inspector = _phase2_check,
) -> dict[str, Any]:
    alpha_config = read_yaml(alpha_config_path)
    rows = collect_scope_rows(
        alpha_config=alpha_config,
        input_root=input_root,
        output_root=output_root,
        holdout_profile=holdout_profile,
        forward_profile=forward_profile,
        max_rows=max_rows,
    )
    existing_outputs = existing_holdout_forward_outputs(output_root)
    if existing_outputs:
        rel_outputs = [rel(path, repo_root) for path in existing_outputs]
        raise ValueError("existing 2025/2026 candidate outputs are forbidden: " + ", ".join(rel_outputs))

    hash_cache: dict[Path, str] = {}
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        raw_evidence = raw_inspector(repo_root=repo_root, row=row, hash_cache=hash_cache)
        phase2_evidence: dict[str, Any] | None = None
        reasons: list[str] = []
        bucket = BLOCKED
        if raw_evidence.get("readiness_status") != raw_readiness.READY_STATUS:
            reasons.extend(str(item) for item in raw_evidence.get("blockers", []))
            reasons.append(f"raw_readiness_status={raw_evidence.get('readiness_status')}")
        else:
            phase2_evidence = phase2_inspector(
                repo_root=repo_root,
                row=row,
                profile=phase2_profile,
                output_root=output_root,
            )
            if phase2_evidence.get("phase2_status") == "PASS":
                bucket = str(row["bucket_if_pass"])
            else:
                reasons.extend(str(item) for item in phase2_evidence.get("failures", []))
                reasons.extend(str(item) for item in phase2_evidence.get("warnings", []))
                reasons.append(f"phase2_status={phase2_evidence.get('phase2_status')}")

        if int(row["year"]) == 2026 and bucket == FORWARD_CANDIDATE:
            reasons.append("partial/current-year forward caveat")

        output_rows.append(
            {
                "profile": row["profile"],
                "market": row["market"],
                "year": row["year"],
                "pair": row["pair"],
                "bucket": bucket,
                "research_use_allowed": False,
                "holdout_use_only": bucket == LOCKED_HOLDOUT_CANDIDATE,
                "forward_use_only": bucket == FORWARD_CANDIDATE,
                "raw_readiness_status": raw_evidence.get("readiness_status"),
                "phase2_status": (phase2_evidence or {}).get("phase2_status"),
                "reasons": reasons,
                "raw_evidence": raw_evidence,
                "phase2_evidence": phase2_evidence,
            }
        )

    counts = {bucket: 0 for bucket in BUCKETS}
    counts.update(Counter(str(row["bucket"]) for row in output_rows))
    status = (
        "PASS"
        if counts[LOCKED_HOLDOUT_CANDIDATE] == EXPECTED_MARKET_COUNT
        and counts[FORWARD_CANDIDATE] == EXPECTED_MARKET_COUNT
        and counts[BLOCKED] == 0
        and counts[NOT_CHECKED] == 0
        else "FAIL"
    )
    return {
        "summary": {
            "stage": "holdout_forward_evidence",
            "status": status,
            "generated_at_utc": generated_at_utc or utc_now(),
            "holdout_profile": holdout_profile,
            "forward_profile": forward_profile,
            "phase2_profile": phase2_profile,
            "expected_rows": max_rows,
            "checked_rows": len(output_rows),
            "bucket_counts": counts,
            "holdout_count": counts[LOCKED_HOLDOUT_CANDIDATE],
            "forward_count": counts[FORWARD_CANDIDATE],
            "blocked_count": counts[BLOCKED],
            "not_checked_count": counts[NOT_CHECKED],
            "input_root": rel(input_root, repo_root),
            "output_root_checked_for_absence": rel(output_root, repo_root),
            "data_mutation_performed": False,
            "parquet_output_written": False,
            "build_approved": False,
            "research_use_allowed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "promotion_approved": False,
            "config_promotion_approved": False,
            "non_approval": NON_APPROVAL,
        },
        "bucket_definitions": {
            LOCKED_HOLDOUT_CANDIDATE: "2025 row passed dry-run evidence; locked holdout only.",
            FORWARD_CANDIDATE: "2026 row passed dry-run evidence; forward/current partial-year only.",
            BLOCKED: "Raw/source or Phase 2 dry-run evidence failed.",
            NOT_CHECKED: "Required evidence was intentionally skipped or unavailable.",
        },
        "rows": output_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    counts = summary["bucket_counts"]
    lines = [
        "# Holdout/Forward Evidence",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Status: `{summary['status']}`.",
        f"- Holdout profile: `{summary['holdout_profile']}`.",
        f"- Forward profile: `{summary['forward_profile']}`.",
        f"- Phase 2 dry-run profile: `{summary['phase2_profile']}`.",
        f"- Bucket counts: `{json.dumps(counts, sort_keys=True)}`.",
        f"- Non-approval: {summary['non_approval']}",
        "",
        "## Safety Flags",
        "",
        "- `data_mutation_performed`: false.",
        "- `parquet_output_written`: false.",
        "- `build_approved`: false.",
        "- `research_use_allowed`: false.",
        "- `modeling_approved`: false.",
        "- `wfa_approved`: false.",
        "- `metrics_approved`: false.",
        "- `predictions_approved`: false.",
        "- `promotion_approved`: false.",
        "- `config_promotion_approved`: false.",
        "",
        "## Rows",
        "",
        "| pair | bucket | raw readiness | phase2 | reasons |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        reasons = "; ".join(str(item) for item in row.get("reasons", []))
        lines.append(
            "| "
            f"{row['pair']} | "
            f"`{row['bucket']}` | "
            f"`{row.get('raw_readiness_status') or ''}` | "
            f"`{row.get('phase2_status') or ''}` | "
            f"{reasons} |"
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
    parser.add_argument("--alpha-config", default=str(DEFAULT_ALPHA_CONFIG))
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--holdout-profile", default=HOLDOUT_PROFILE)
    parser.add_argument("--forward-profile", default=FORWARD_PROFILE)
    parser.add_argument("--phase2-profile", default="all_raw")
    parser.add_argument("--max-rows", type=int, default=EXPECTED_ROW_COUNT)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_evidence(
            repo_root=repo_root,
            alpha_config_path=resolve_path(repo_root, args.alpha_config),
            input_root=resolve_path(repo_root, args.input_root),
            output_root=resolve_path(repo_root, args.output_root),
            holdout_profile=str(args.holdout_profile),
            forward_profile=str(args.forward_profile),
            phase2_profile=str(args.phase2_profile),
            max_rows=int(args.max_rows),
        )
    except ValueError as exc:
        print(f"FAIL holdout_forward_evidence: {exc}")
        return 1

    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "holdout_forward_evidence "
        f"status={summary['status']} "
        f"holdout={summary['holdout_count']} "
        f"forward={summary['forward_count']} "
        f"blocked={summary['blocked_count']} "
        f"not_checked={summary['not_checked_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
