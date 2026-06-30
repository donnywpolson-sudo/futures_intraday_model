#!/usr/bin/env python3
"""Report-only adversarial audit for tier research/holdout/forward splits."""

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
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_ALPHA_CONFIG = REPO_ROOT / "configs/alpha_tiered.yaml"
DEFAULT_DATA_MANIFEST = REPO_ROOT / "configs/data_manifest.yaml"
DEFAULT_PREBUILD_PLAN = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_prebuild_plan.json"
DEFAULT_RAW_READINESS = REPO_ROOT / REVIEW_ROOT / "broad_manifest_527_rebuild_raw_source_readiness.json"
DEFAULT_FINAL_INCLUDE = (
    REPO_ROOT
    / REVIEW_ROOT
    / "broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json"
)
DEFAULT_FINAL_READINESS = (
    REPO_ROOT
    / REVIEW_ROOT
    / "broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_sparse_roll_window_policy.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data/causal_base_candidates/broad_manifest_527_rebuild_v1"
DEFAULT_AUDIT_ROOT = REPO_ROOT / "reports/data_audit/tier_research_ladder_audit"
DEFAULT_JSON_OUT = DEFAULT_AUDIT_ROOT / "tier_research_ladder_audit.json"
DEFAULT_MD_OUT = DEFAULT_AUDIT_ROOT / "tier_research_ladder_audit.md"

RESEARCH_VALID = "research_valid"
LOCKED_HOLDOUT_CANDIDATE = "locked_holdout_candidate"
FORWARD_CANDIDATE = "forward_candidate"
BLOCKED = "blocked"
NOT_CHECKED = "not_checked"
BUCKETS = [
    RESEARCH_VALID,
    LOCKED_HOLDOUT_CANDIDATE,
    FORWARD_CANDIDATE,
    BLOCKED,
    NOT_CHECKED,
]

NON_APPROVAL = (
    "This report-only tier audit does not approve config promotion, modeling, "
    "WFA, predictions, metrics, staging, commits, production/live use, or "
    "research use for holdout/forward rows."
)


RawInspector = Callable[..., dict[str, Any]]
Phase2Inspector = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


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


def _pair(row: dict[str, Any]) -> str:
    return str(row.get("pair") or f"{row['market']}:{int(row['year'])}")


def _market_years(payload: dict[str, Any]) -> set[str]:
    rows = payload.get("market_years")
    if not isinstance(rows, list):
        return set()
    return {f"{row['market']}:{int(row['year'])}" for row in rows}


def _profile_summary(alpha_config: dict[str, Any]) -> dict[str, Any]:
    profiles = alpha_config.get("profiles", {})
    if not isinstance(profiles, dict):
        return {"status": "FAIL", "profiles": {}, "findings": ["profiles missing"]}
    names = [
        "tier_1_research",
        "tier_1_holdout",
        "tier_1_forward",
        "tier_2_research",
        "tier_2_holdout",
        "tier_2_forward",
        "tier_3_research",
        "tier_3_holdout",
        "tier_3_forward",
    ]
    summary: dict[str, Any] = {}
    findings: list[str] = []
    for name in names:
        profile = profiles.get(name)
        if not isinstance(profile, dict):
            findings.append(f"{name} missing")
            continue
        years = [int(year) for year in profile.get("years", [])]
        summary[name] = {
            "description": profile.get("description"),
            "intent": profile.get("intent"),
            "market_count": len(profile.get("markets", []) or []),
            "years": years,
            "forbid_research_use": bool(profile.get("forbid_research_use", False)),
        }
        if name.endswith("_research") and any(year in (2025, 2026) for year in years):
            findings.append(f"{name} includes 2025/2026 in research years")
        if name.endswith("_holdout") and years != [2025]:
            findings.append(f"{name} holdout years are {years!r}, expected [2025]")
        if name.endswith("_forward") and years != [2026]:
            findings.append(f"{name} forward years are {years!r}, expected [2026]")
        if (name.endswith("_holdout") or name.endswith("_forward")) and not bool(
            profile.get("forbid_research_use", False)
        ):
            findings.append(f"{name} missing forbid_research_use=true")
    return {"status": "PASS" if not findings else "FAIL", "profiles": summary, "findings": findings}


def _phase2_check(
    *,
    repo_root: Path,
    row: dict[str, Any],
    profile: str,
    output_root: Path,
) -> dict[str, Any]:
    market = str(row["market"])
    year = int(row["year"])
    raw_path = resolve_path(repo_root, str(row["planned_input_raw_path"]))
    output_path = output_root / market / f"{year}.parquet"
    result = process_file(
        raw_path,
        output_path,
        profile=profile,
        write_output=False,
    )
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


def _bucket_historical_row(
    *,
    row: dict[str, Any],
    final_pass_pairs: set[str],
    raw_rows_by_pair: dict[str, dict[str, Any]],
) -> tuple[str, list[str], dict[str, Any]]:
    pair = _pair(row)
    if pair == "6M:2012":
        return BLOCKED, ["confirmed roll-maturity backstep excluded from final 460-row scope"], {}
    if pair in final_pass_pairs:
        return RESEARCH_VALID, [], {"phase2_status": "PASS"}
    raw_row = raw_rows_by_pair.get(pair)
    if raw_row is None:
        return NOT_CHECKED, ["missing raw/source readiness row"], {}
    raw_status = str(raw_row.get("readiness_status"))
    if raw_status != raw_readiness.READY_STATUS:
        return BLOCKED, [*raw_row.get("blockers", []), f"raw readiness status={raw_status}"], {}
    return NOT_CHECKED, ["raw/source ready but not in final Phase 2 PASS include"], {}


def _bucket_deferred_row(
    *,
    row: dict[str, Any],
    raw_evidence: dict[str, Any] | None,
    phase2_evidence: dict[str, Any] | None,
    inspect_phase2: bool,
) -> tuple[str, list[str], dict[str, Any]]:
    year = int(row["year"])
    if raw_evidence is None:
        return NOT_CHECKED, ["deferred raw/source inspection was not run"], {}
    raw_status = str(raw_evidence.get("readiness_status"))
    if raw_status != raw_readiness.READY_STATUS:
        return BLOCKED, [*raw_evidence.get("blockers", []), f"raw readiness status={raw_status}"], {}
    if not inspect_phase2:
        return NOT_CHECKED, ["raw/source ready but deferred Phase 2 readiness was not run"], {}
    if phase2_evidence is None:
        return NOT_CHECKED, ["raw/source ready but missing deferred Phase 2 evidence"], {}
    phase2_status = str(phase2_evidence.get("phase2_status"))
    if phase2_status != "PASS":
        reasons = [
            *phase2_evidence.get("failures", []),
            *phase2_evidence.get("warnings", []),
            f"phase2_status={phase2_status}",
        ]
        return BLOCKED, reasons, {}
    if year == 2025:
        return LOCKED_HOLDOUT_CANDIDATE, [], {"phase2_status": "PASS"}
    if year == 2026:
        return FORWARD_CANDIDATE, ["partial/current-year forward caveat"], {"phase2_status": "PASS"}
    return NOT_CHECKED, [f"unexpected deferred year={year}"], {}


def build_audit(
    *,
    repo_root: Path,
    alpha_config_path: Path,
    data_manifest_path: Path,
    prebuild_plan_path: Path,
    raw_readiness_path: Path,
    final_include_path: Path,
    final_readiness_path: Path,
    output_root: Path,
    generated_at_utc: str | None = None,
    inspect_deferred_phase2: bool = True,
    phase2_profile: str = "all_raw",
    raw_inspector: RawInspector = raw_readiness.validate_action_required_row,
    phase2_inspector: Phase2Inspector = _phase2_check,
) -> dict[str, Any]:
    alpha_config = read_yaml(alpha_config_path)
    data_manifest = read_yaml(data_manifest_path)
    prebuild_plan = read_json(prebuild_plan_path)
    raw_report = read_json(raw_readiness_path)
    final_include = read_json(final_include_path)
    final_readiness = read_json(final_readiness_path)

    prebuild_rows = prebuild_plan.get("rows")
    if not isinstance(prebuild_rows, list):
        raise ValueError("prebuild plan rows missing")
    raw_rows = raw_report.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("raw readiness rows missing")
    raw_rows_by_pair = {_pair(row): row for row in raw_rows}
    final_status = final_readiness.get("status")
    final_pass_pairs = _market_years(final_include) if final_status == "PASS" else set()

    hash_cache: dict[Path, str] = {}
    rows: list[dict[str, Any]] = []
    deferred_phase2_checked = 0
    deferred_raw_checked = 0
    for row in prebuild_rows:
        market = str(row["market"])
        year = int(row["year"])
        pair = _pair(row)
        prebuild_status = str(row.get("prebuild_status"))
        raw_evidence = None
        phase2_evidence = None
        extra: dict[str, Any] = {}
        if prebuild_status == "deferred_policy_review":
            raw_evidence = raw_inspector(repo_root=repo_root, row=row, hash_cache=hash_cache)
            deferred_raw_checked += 1
            if (
                inspect_deferred_phase2
                and raw_evidence.get("readiness_status") == raw_readiness.READY_STATUS
            ):
                phase2_evidence = phase2_inspector(
                    repo_root=repo_root,
                    row=row,
                    profile=phase2_profile,
                    output_root=output_root,
                )
                deferred_phase2_checked += 1
            bucket, reasons, extra = _bucket_deferred_row(
                row=row,
                raw_evidence=raw_evidence,
                phase2_evidence=phase2_evidence,
                inspect_phase2=inspect_deferred_phase2,
            )
        elif year <= 2024:
            bucket, reasons, extra = _bucket_historical_row(
                row=row,
                final_pass_pairs=final_pass_pairs,
                raw_rows_by_pair=raw_rows_by_pair,
            )
        else:
            bucket = NOT_CHECKED
            reasons = [f"unexpected non-deferred future row status={prebuild_status}"]

        rows.append(
            {
                "market": market,
                "year": year,
                "pair": pair,
                "bucket": bucket,
                "prebuild_status": prebuild_status,
                "research_use_allowed": bucket == RESEARCH_VALID,
                "holdout_use_only": bucket == LOCKED_HOLDOUT_CANDIDATE,
                "forward_use_only": bucket == FORWARD_CANDIDATE,
                "raw_readiness_status": (
                    raw_evidence or raw_rows_by_pair.get(pair, {})
                ).get("readiness_status"),
                "phase2_status": (phase2_evidence or extra).get("phase2_status"),
                "reasons": reasons,
                "raw_evidence": raw_evidence,
                "phase2_evidence": phase2_evidence,
            }
        )

    counts = {bucket: 0 for bucket in BUCKETS}
    counts.update(Counter(row["bucket"] for row in rows))
    duplicate_pairs = [
        pair for pair, count in Counter(row["pair"] for row in rows).items() if count != 1
    ]
    expected_rows = len(rows)
    status = "FAIL" if duplicate_pairs or counts[BLOCKED] else "PASS"
    if counts[NOT_CHECKED]:
        status = "WARN" if status == "PASS" else status

    return {
        "summary": {
            "stage": "tier_research_ladder_adversarial_audit",
            "status": status,
            "generated_at_utc": generated_at_utc or utc_now(),
            "expected_market_years": expected_rows,
            "bucket_counts": counts,
            "deferred_raw_checked": deferred_raw_checked,
            "deferred_phase2_checked": deferred_phase2_checked,
            "final_phase2_readiness_status": final_status,
            "final_phase2_selected_count": final_readiness.get("selected_market_year_count"),
            "final_phase2_checked_count": final_readiness.get("checked_market_year_count"),
            "final_include_count": len(final_pass_pairs),
            "blocked_pairs": [row["pair"] for row in rows if row["bucket"] == BLOCKED],
            "not_checked_pairs": [row["pair"] for row in rows if row["bucket"] == NOT_CHECKED],
            "holdout_pairs": [
                row["pair"] for row in rows if row["bucket"] == LOCKED_HOLDOUT_CANDIDATE
            ],
            "forward_pairs": [row["pair"] for row in rows if row["bucket"] == FORWARD_CANDIDATE],
            "duplicate_pairs": duplicate_pairs,
            "data_mutation_performed": False,
            "build_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed_for_holdout_forward": False,
            "non_approval": NON_APPROVAL,
        },
        "inputs": {
            "alpha_config": rel(alpha_config_path, repo_root),
            "data_manifest": rel(data_manifest_path, repo_root),
            "prebuild_plan": rel(prebuild_plan_path, repo_root),
            "raw_readiness": rel(raw_readiness_path, repo_root),
            "final_include": rel(final_include_path, repo_root),
            "final_readiness": rel(final_readiness_path, repo_root),
            "output_root_checked_for_write": rel(output_root, repo_root),
            "data_manifest_source_profile": data_manifest.get("source_profile"),
        },
        "profile_audit": _profile_summary(alpha_config),
        "bucket_definitions": {
            RESEARCH_VALID: "Phase 2-ready historical row allowed for research; not build/promotion approval.",
            LOCKED_HOLDOUT_CANDIDATE: "2025 row passed inspection; locked holdout only, no tuning/model selection.",
            FORWARD_CANDIDATE: "2026 row passed inspection; forward/current validation only with partial-year caveat.",
            BLOCKED: "Data or policy blocker prevents use until separately resolved.",
            NOT_CHECKED: "Required inspection evidence is missing or intentionally skipped.",
        },
        "adversarial_findings": [
            "2024 is stale for a current-data claim, but acceptable as historical research cutoff.",
            "2025 holdout rows must not influence feature, threshold, model, market, or config selection.",
            "2026 forward rows must not be treated as a full historical year.",
            "A valid data row is not automatically a research-eligible row.",
        ],
        "rows": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    counts = summary["bucket_counts"]
    lines = [
        "# Tier Research Ladder Adversarial Audit",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Status: `{summary['status']}`",
        f"- Bucket counts: `{json.dumps(counts, sort_keys=True)}`",
        f"- Deferred raw/source rows checked: {summary['deferred_raw_checked']}",
        f"- Deferred Phase 2 rows checked: {summary['deferred_phase2_checked']}",
        f"- Final Phase 2 readiness: `{summary['final_phase2_readiness_status']}`",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false",
        "- `build_approved`: false",
        "- `broader_modeling_approved`: false",
        "- `config_promotion_approved`: false",
        "",
        "## Adversarial Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in report["adversarial_findings"])
    lines.extend(
        [
            "",
            "## Bucket Counts",
            "",
            "| bucket | count |",
            "| --- | ---: |",
        ]
    )
    for bucket in BUCKETS:
        lines.append(f"| `{bucket}` | {counts.get(bucket, 0)} |")
    lines.extend(["", "## Blocked And Not Checked", ""])
    for label, key in [("Blocked", "blocked_pairs"), ("Not checked", "not_checked_pairs")]:
        pairs = summary[key]
        lines.append(f"- {label}: {', '.join(pairs) if pairs else 'None'}")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| pair | bucket | raw readiness | phase2 | reasons |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
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
    parser.add_argument("--data-manifest", default=str(DEFAULT_DATA_MANIFEST))
    parser.add_argument("--prebuild-plan", default=str(DEFAULT_PREBUILD_PLAN))
    parser.add_argument("--raw-readiness", default=str(DEFAULT_RAW_READINESS))
    parser.add_argument("--final-include", default=str(DEFAULT_FINAL_INCLUDE))
    parser.add_argument("--final-readiness", default=str(DEFAULT_FINAL_READINESS))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--phase2-profile", default="all_raw")
    parser.add_argument("--skip-deferred-phase2", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MD_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    report = build_audit(
        repo_root=repo_root,
        alpha_config_path=resolve_path(repo_root, args.alpha_config),
        data_manifest_path=resolve_path(repo_root, args.data_manifest),
        prebuild_plan_path=resolve_path(repo_root, args.prebuild_plan),
        raw_readiness_path=resolve_path(repo_root, args.raw_readiness),
        final_include_path=resolve_path(repo_root, args.final_include),
        final_readiness_path=resolve_path(repo_root, args.final_readiness),
        output_root=resolve_path(repo_root, args.output_root),
        inspect_deferred_phase2=not args.skip_deferred_phase2,
        phase2_profile=str(args.phase2_profile),
    )
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "tier_research_ladder_audit "
        f"status={summary['status']} "
        f"bucket_counts={json.dumps(summary['bucket_counts'], sort_keys=True)} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0 if summary["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
