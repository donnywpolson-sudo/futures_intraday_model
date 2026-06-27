#!/usr/bin/env python3
"""Refresh the master data health matrix from existing local evidence only."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "data_manifest.yaml"
DEFAULT_MATRIX = REPO_ROOT / "reports" / "data_manifest" / "master_data_health_matrix.json"
DEFAULT_SUMMARY = REPO_ROOT / "reports" / "data_manifest" / "master_data_health_summary.md"
DEFAULT_RAW_AUDIT = REPO_ROOT / "reports" / "raw_readiness" / "raw_enriched_optional_schema_audit.json"
DEFAULT_PHASE2_PLAN = REPO_ROOT / "reports" / "phase_restart" / "batch_phase2_build_exclusion_plan.json"
DEFAULT_HANDOFF = REPO_ROOT / "CODEX_HANDOFF.md"


@dataclass(frozen=True, order=True)
class Pair:
    market: str
    year: int

    @classmethod
    def parse(cls, value: str) -> "Pair":
        cleaned = value.strip().replace("`", "")
        if ":" in cleaned:
            market, year = cleaned.split(":", 1)
        else:
            market, year = cleaned.split()
        return cls(str(market), int(year))

    def text(self) -> str:
        return f"{self.market}:{self.year}"

    def label(self) -> str:
        return f"{self.market} {self.year}"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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
        start = overrides.get(market, default_start)
        pairs.extend(Pair(market, year) for year in range(start, end_year + 1))
    return pairs


def truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def bool_text(value: bool) -> str:
    return "True" if value else "False"


def pair_path(repo_root: Path, pattern: str, pair: Pair) -> Path:
    path = pattern.replace("{market}", pair.market).replace("{year}", str(pair.year))
    return resolve_path(repo_root, path)


def current_causal_pairs(repo_root: Path, pattern: str, pairs: Iterable[Pair]) -> set[Pair]:
    return {pair for pair in pairs if pair_path(repo_root, pattern, pair).exists()}


def _expand_handoff_entries(value: str) -> list[Pair]:
    pairs: list[Pair] = []
    if not value.strip():
        return pairs
    for raw in value.split(","):
        token = raw.strip().strip("`")
        match = re.fullmatch(r"([A-Za-z0-9]+)\s+(\d{4})(?:-(\d{4}))?", token)
        if not match:
            raise ValueError(f"unsupported handoff row token: {token}")
        market = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3) or start)
        if end < start:
            raise ValueError(f"invalid handoff range: {token}")
        pairs.extend(Pair(market, year) for year in range(start, end + 1))
    return pairs


def _latest_reconciliation_section(handoff_text: str) -> str:
    marker = "## Latest Global Phase 1-2 Completion Reconciliation Result"
    start = handoff_text.rfind(marker)
    if start < 0:
        raise ValueError(f"missing handoff section: {marker}")
    rest = handoff_text[start:]
    next_heading = rest.find("\n## ", 1)
    return rest if next_heading < 0 else rest[:next_heading]


def _parse_handoff_list(section: str, key: str) -> list[Pair]:
    pattern = rf"`{re.escape(key)}`:\s*(\d+)\s+rows(?:\s+\(([^\n]*)\))?"
    match = re.search(pattern, section)
    if not match:
        raise ValueError(f"missing handoff list: {key}")
    expected_count = int(match.group(1))
    pairs = _expand_handoff_entries(match.group(2) or "")
    if len(pairs) != expected_count:
        raise ValueError(
            f"handoff {key} count mismatch: declared {expected_count}, parsed {len(pairs)}"
        )
    return pairs


def parse_handoff_scope(handoff_text: str) -> dict[str, list[Pair]]:
    section = _latest_reconciliation_section(handoff_text)
    return {
        "canonical_phase2_pass": _parse_handoff_list(section, "canonical_phase2_pass"),
        "fail_closed_with_decision_packet": _parse_handoff_list(section, "fail_closed_with_decision_packet"),
        "unresolved": _parse_handoff_list(section, "unresolved"),
    }


def _count_rows(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if truthy(row.get(field)))


def _row_pair(row: dict[str, Any]) -> Pair:
    if row.get("pair"):
        return Pair.parse(str(row["pair"]))
    return Pair(str(row["market"]), int(row["year"]))


def _health_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("health_class") or "UNKNOWN_REVIEW_REQUIRED")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _raw_optional_summary(raw_audit_path: Path, raw_audit: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    summary = raw_audit.get("summary") if isinstance(raw_audit.get("summary"), dict) else {}
    return {
        "path": rel(raw_audit_path, repo_root),
        "status": raw_audit.get("status", ""),
        "file_count": raw_audit.get("file_count"),
        "row_count": raw_audit.get("row_count"),
        "summary": summary,
        "failing_pairs": raw_audit.get("failing_pairs", []),
    }


def _phase2_plan_summary(plan_path: Path, phase2_plan: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    counts = phase2_plan.get("counts") if isinstance(phase2_plan.get("counts"), dict) else {}
    return {
        "path": rel(plan_path, repo_root),
        "accepted_rows": counts.get("accepted_rows_for_future_bounded_phase2_build_approval", 0),
        "deferred_excluded_rows": counts.get("deferred_excluded_rows", 0),
        "accepted_rows_with_pre_build_raw_evidence_prerequisite": counts.get(
            "accepted_rows_with_pre_build_raw_evidence_prerequisite", 0
        ),
        "phase2_build_commands_run": counts.get("phase2_build_commands_run", 0),
        "cleanup_commands_run": counts.get("cleanup_commands_run", 0),
    }


def _format_rows(pairs: Iterable[Pair]) -> list[str]:
    return [pair.text() for pair in pairs]


def refresh(
    *,
    repo_root: Path,
    manifest_path: Path,
    matrix_path: Path,
    summary_path: Path,
    raw_audit_path: Path,
    phase2_plan_path: Path,
    handoff_path: Path,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    manifest = read_yaml(manifest_path)
    matrix = read_json(matrix_path)
    raw_audit = read_json(raw_audit_path)
    phase2_plan = read_json(phase2_plan_path)
    handoff_scope = parse_handoff_scope(handoff_path.read_text(encoding="utf-8"))

    expected = expected_pairs(manifest)
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{matrix_path} is missing rows list")

    row_by_pair = {_row_pair(row).text(): row for row in rows if isinstance(row, dict)}
    missing = [pair.text() for pair in expected if pair.text() not in row_by_pair]
    if missing:
        raise ValueError(f"baseline matrix missing expected rows: {', '.join(missing[:20])}")

    causal_pattern = str(manifest["canonical_paths"]["causal_parquet_pattern"])
    causal_present = current_causal_pairs(repo_root, causal_pattern, expected)
    refreshed_rows: list[dict[str, Any]] = []
    for pair in expected:
        row = dict(row_by_pair[pair.text()])
        row["market"] = pair.market
        row["year"] = str(pair.year)
        row["pair"] = pair.text()
        row["causal_parquet_present"] = bool_text(pair in causal_present)
        refreshed_rows.append(row)

    schema_counts = {
        "raw_parquet_present": _count_rows(refreshed_rows, "raw_parquet_present"),
        "causal_parquet_present": len(causal_present),
        "ohlcv_1m_dbn_present": _count_rows(refreshed_rows, "ohlcv_1m_dbn_present"),
        "definition_dbn_present": _count_rows(refreshed_rows, "definition_dbn_present"),
        "statistics_dbn_present": _count_rows(refreshed_rows, "statistics_dbn_present"),
        "status_dbn_present": _count_rows(refreshed_rows, "status_dbn_present"),
    }
    status_missing = [pair for pair, row in zip(expected, refreshed_rows) if not truthy(row.get("status_dbn_present"))]
    prior_summary = matrix.get("summary") if isinstance(matrix.get("summary"), dict) else {}
    prior_schema_counts = prior_summary.get("schema_presence_counts") if isinstance(prior_summary.get("schema_presence_counts"), dict) else {}
    prior_stale = prior_summary.get("stale_causal_coverage_correction") if isinstance(prior_summary.get("stale_causal_coverage_correction"), dict) else {}
    prior_causal_count = int(
        prior_stale.get("prior_matrix_causal_parquet_present", prior_schema_counts.get("causal_parquet_present", 0)) or 0
    )
    prior_matrix_generated_at = (
        prior_stale.get("prior_matrix_generated_at_utc")
        or prior_summary.get("source_matrix_generated_at_utc")
        or prior_summary.get("generated_at_utc")
    )
    raw_summary = raw_audit.get("summary") if isinstance(raw_audit.get("summary"), dict) else {}
    pass_rows = handoff_scope["canonical_phase2_pass"]
    pass_present = [pair for pair in pass_rows if pair in causal_present]

    generated_at = generated_at_utc or utc_now()
    summary = dict(prior_summary)
    summary.update(
        {
            "generated_at_utc": generated_at,
            "scope": "report-only master data health refresh from existing local evidence; no data mutation",
            "source_matrix_generated_at_utc": prior_matrix_generated_at,
            "expected_rows": len(expected),
            "health_class_counts": _health_counts(refreshed_rows),
            "schema_presence_counts": schema_counts,
            "raw_optional_audit": _raw_optional_summary(raw_audit_path, raw_audit, repo_root),
            "phase2_plan": _phase2_plan_summary(phase2_plan_path, phase2_plan, repo_root),
            "current_canonical_causal": {
                "pattern": causal_pattern,
                "present_count": len(causal_present),
                "missing_count": len(expected) - len(causal_present),
                "present_rows": _format_rows(pair for pair in expected if pair in causal_present),
            },
            "status_dbn_gaps": {
                "missing_count": len(status_missing),
                "missing_rows": _format_rows(status_missing),
            },
            "status_dbn_audit_reconciliation": {
                "matrix_status_dbn_present": schema_counts["status_dbn_present"],
                "matrix_status_dbn_missing": len(status_missing),
                "raw_optional_status_archive_market_year_count": raw_summary.get("status_archive_market_year_count"),
                "raw_optional_missing_status_archive_market_year_count": raw_summary.get("missing_status_archive_market_year_count"),
                "scope_note": "matrix status_dbn_present preserves baseline manifest DBN path evidence; raw optional audit reports raw-enrichment archive evidence",
            },
            "approved_phase1_2_scope": {
                "source": rel(handoff_path, repo_root),
                "canonical_phase2_pass_count": len(pass_rows),
                "canonical_phase2_pass_rows": _format_rows(pass_rows),
                "canonical_phase2_pass_causal_present_count": len(pass_present),
                "canonical_phase2_pass_missing_causal_rows": _format_rows(
                    pair for pair in pass_rows if pair not in causal_present
                ),
                "fail_closed_with_decision_packet_count": len(
                    handoff_scope["fail_closed_with_decision_packet"]
                ),
                "fail_closed_with_decision_packet_rows": _format_rows(
                    handoff_scope["fail_closed_with_decision_packet"]
                ),
                "unresolved_count": len(handoff_scope["unresolved"]),
                "unresolved_rows": _format_rows(handoff_scope["unresolved"]),
            },
            "stale_causal_coverage_correction": {
                "prior_matrix_causal_parquet_present": prior_causal_count,
                "current_canonical_causal_present": len(causal_present),
                "difference": len(causal_present) - prior_causal_count,
                "prior_matrix_generated_at_utc": prior_matrix_generated_at,
            },
        }
    )

    output = {"summary": summary, "rows": refreshed_rows}
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(render_markdown(output), encoding="utf-8")
    return output


def render_markdown(matrix: dict[str, Any]) -> str:
    summary = matrix["summary"]
    counts = summary["health_class_counts"]
    schema = summary["schema_presence_counts"]
    raw = summary["raw_optional_audit"]
    raw_summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    phase2 = summary["phase2_plan"]
    causal = summary["current_canonical_causal"]
    status = summary["status_dbn_gaps"]
    approved = summary["approved_phase1_2_scope"]
    stale = summary["stale_causal_coverage_correction"]
    status_recon = summary["status_dbn_audit_reconciliation"]
    expected = int(summary["expected_rows"])

    lines = [
        "# Master Data Health Matrix",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: report-only master data health refresh from existing local evidence.",
        "- Safety: no repair, Phase 2 build, cleanup, redownload, move, merge, quarantine, delete, or DBN/source modification was run by this refresh.",
        "",
        "## Raw/Source Completeness",
        "",
        f"- Expected market/year rows: {expected}.",
        f"- `OK_SOURCE_PRESENT`: {counts.get('OK_SOURCE_PRESENT', 0)}.",
        f"- `POLICY_REVIEW_REQUIRED`: {counts.get('POLICY_REVIEW_REQUIRED', 0)}.",
        f"- `EXCLUDED_FROM_PHASE2`: {counts.get('EXCLUDED_FROM_PHASE2', 0)}.",
        f"- `UNKNOWN_REVIEW_REQUIRED`: {counts.get('UNKNOWN_REVIEW_REQUIRED', 0)}.",
        f"- `raw_parquet_present`: {schema['raw_parquet_present']}/{expected}.",
        f"- `ohlcv_1m_dbn_present`: {schema['ohlcv_1m_dbn_present']}/{expected}.",
        f"- `definition_dbn_present`: {schema['definition_dbn_present']}/{expected}.",
        f"- `statistics_dbn_present`: {schema['statistics_dbn_present']}/{expected}.",
        f"- `status_dbn_present`: {schema['status_dbn_present']}/{expected}; missing {status['missing_count']} rows.",
        "",
        "## Current Canonical Phase 2 Causal Coverage",
        "",
        f"- `causal_parquet_present`: {causal['present_count']}/{expected}.",
        f"- Missing canonical causal parquet rows: {causal['missing_count']}.",
        f"- Current build plan accepted rows: {phase2['accepted_rows']}; deferred rows: {phase2['deferred_excluded_rows']}.",
        f"- Accepted rows still requiring pre-build raw evidence: {phase2['accepted_rows_with_pre_build_raw_evidence_prerequisite']}.",
        "",
        "## Approved Phase 1-2 Scope",
        "",
        f"- Approved PASS rows: {approved['canonical_phase2_pass_count']}.",
        f"- Approved PASS rows with current canonical causal parquet: {approved['canonical_phase2_pass_causal_present_count']}/{approved['canonical_phase2_pass_count']}.",
        f"- Fail-closed rows with decision packet: {approved['fail_closed_with_decision_packet_count']}.",
        f"- Unresolved rows: {approved['unresolved_count']}.",
        f"- PASS rows: {', '.join(approved['canonical_phase2_pass_rows']) or 'None'}.",
        f"- Fail-closed rows: {', '.join(approved['fail_closed_with_decision_packet_rows']) or 'None'}.",
        f"- Unresolved rows: {', '.join(approved['unresolved_rows']) or 'None'}.",
        "",
        "## Raw Optional-Schema Audit",
        "",
        f"- Status: `{raw.get('status', '')}` from `{raw.get('path', '')}`.",
        f"- Files checked: {raw.get('file_count')}; rows checked: {raw.get('row_count')}.",
    ]
    for key in sorted(raw_summary):
        lines.append(f"- `{key}`: {raw_summary[key]}.")
    lines.extend(
        [
            "",
            "## Stale/Conflicting Prior Matrix Evidence",
            "",
            f"- Prior matrix generated at UTC: {stale.get('prior_matrix_generated_at_utc')}.",
            f"- Prior `causal_parquet_present`: {stale['prior_matrix_causal_parquet_present']}/{expected}.",
            f"- Current canonical `causal_parquet_present`: {stale['current_canonical_causal_present']}/{expected}.",
            f"- Correction: {stale['difference']} rows versus the prior matrix count.",
            f"- Matrix row-level `status_dbn_present`: {status_recon['matrix_status_dbn_present']}/{expected}; current raw optional audit `status_archive_market_year_count`: {status_recon['raw_optional_status_archive_market_year_count']} and `missing_status_archive_market_year_count`: {status_recon['raw_optional_missing_status_archive_market_year_count']}.",
            "- Status DBN counts are separate evidence scopes and are preserved rather than merged.",
            "",
            "## Safety",
            "",
            "- No Phase 2 build was run.",
            "- No cleanup was run.",
            "- No data file was moved, deleted, merged, quarantined, rebuilt, or redownloaded.",
            "- DBN source files were not modified by this refresh.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--raw-audit", default=str(DEFAULT_RAW_AUDIT))
    parser.add_argument("--phase2-plan", default=str(DEFAULT_PHASE2_PLAN))
    parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF))
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    output = refresh(
        repo_root=repo_root,
        manifest_path=resolve_path(repo_root, args.manifest),
        matrix_path=resolve_path(repo_root, args.matrix),
        summary_path=resolve_path(repo_root, args.summary),
        raw_audit_path=resolve_path(repo_root, args.raw_audit),
        phase2_plan_path=resolve_path(repo_root, args.phase2_plan),
        handoff_path=resolve_path(repo_root, args.handoff),
    )
    summary = output["summary"]
    print(
        "master_data_health_refresh "
        f"expected_rows={summary['expected_rows']} "
        f"causal_parquet_present={summary['current_canonical_causal']['present_count']} "
        f"approved_pass={summary['approved_phase1_2_scope']['canonical_phase2_pass_count']} "
        f"fail_closed={summary['approved_phase1_2_scope']['fail_closed_with_decision_packet_count']} "
        f"unresolved={summary['approved_phase1_2_scope']['unresolved_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
