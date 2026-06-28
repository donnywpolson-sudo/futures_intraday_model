#!/usr/bin/env python3
"""Bounded checker for the canonical Phase 1A/1B/1C/2 data manifest.

The checker reads manifest policy plus the lineage coverage CSV, then derives
market/year coverage from filenames only. It does not open DBN or parquet
payloads and does not mutate data.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "configs" / "data_manifest.yaml"
DEFAULT_COVERAGE = ROOT / "reports" / "data_lineage" / "expected_vs_actual_coverage.csv"
DEFAULT_REPORTS_ROOT = ROOT / "reports" / "data_manifest"
DEFAULT_PROFILE_CONFIG = ROOT / "configs" / "alpha_tiered.yaml"


@dataclass(frozen=True, order=True)
class Pair:
    market: str
    year: int

    @classmethod
    def parse(cls, value: str) -> "Pair":
        market, year = value.split(":", 1)
        return cls(market=market, year=int(year))

    def text(self) -> str:
        return f"{self.market}:{self.year}"


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def read_coverage_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def expected_pairs(manifest: dict[str, Any]) -> set[Pair]:
    markets = [str(item) for item in manifest["expected_markets"]]
    years = manifest["expected_years"]
    default_start = int(years["default_start_year"])
    end_year = int(years["end_year"])
    overrides = {
        str(market): int(start)
        for market, start in (years.get("market_start_year_overrides") or {}).items()
    }
    return {
        Pair(market, year)
        for market in markets
        for year in range(overrides.get(market, default_start), end_year + 1)
    }


def expected_trade_pairs(manifest: dict[str, Any]) -> set[Pair]:
    markets = [str(item) for item in manifest["expected_markets"]]
    years = [int(year) for year in manifest["schemas"]["trades"]["expected_years"]]
    return {Pair(market, year) for market in markets for year in years}


def dbn_pairs(root: Path, path_name: str) -> tuple[set[Pair], dict[Pair, list[Path]]]:
    base = root / path_name
    pairs: set[Pair] = set()
    pair_paths: dict[Pair, list[Path]] = defaultdict(list)
    if not base.exists():
        return pairs, pair_paths
    for path in sorted(base.glob("**/*.dbn.zst")):
        parts = path.relative_to(base).parts
        pair: Pair | None = None
        if len(parts) >= 3 and parts[1].isdigit():
            pair = Pair(parts[0], int(parts[1]))
        elif len(parts) >= 4 and parts[2].isdigit():
            pair = Pair(parts[1], int(parts[2]))
        if pair is None:
            continue
        pairs.add(pair)
        pair_paths[pair].append(path)
    return pairs, pair_paths


def parquet_pairs(pattern: str) -> set[Pair]:
    marker = "{market}/{year}.parquet"
    if marker not in pattern:
        raise ValueError(f"unsupported parquet pattern: {pattern}")
    base = ROOT / pattern.split("{market}", 1)[0].rstrip("/\\")
    pairs: set[Pair] = set()
    if not base.exists():
        return pairs
    for path in sorted(base.glob("*/*.parquet")):
        market = path.parent.name
        if market.startswith("_") or not path.stem.isdigit():
            continue
        pairs.add(Pair(market, int(path.stem)))
    return pairs


def pair_set(raw_values: Iterable[str]) -> set[Pair]:
    return {Pair.parse(str(value)) for value in raw_values or []}


def allowed_extra_pairs(manifest: dict[str, Any], schema_name: str) -> set[Pair]:
    raw = (
        manifest.get("coverage_policy", {})
        .get("extra_pairs", {})
        .get("allowed_extra_pairs", {})
        .get(schema_name, [])
    )
    return pair_set(raw)


def known_duplicate_pairs(manifest: dict[str, Any], schema_name: str) -> set[Pair]:
    raw = (
        manifest.get("coverage_policy", {})
        .get("duplicates", {})
        .get("known_duplicate_pairs", {})
        .get(schema_name, [])
    )
    return pair_set(raw)


def allowed_missing_pairs(manifest: dict[str, Any], artifact_name: str) -> set[Pair]:
    raw = (
        manifest.get("coverage_policy", {})
        .get("missing_pairs", {})
        .get("allowed_missing_pairs", {})
        .get(artifact_name, [])
    )
    return pair_set(raw)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def issue_rows_for_artifact(
    *,
    artifact: str,
    schema: str,
    expected: set[Pair],
    actual: set[Pair],
    pair_paths: dict[Pair, list[Path]] | None,
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    allowed_missing = allowed_missing_pairs(manifest, artifact)
    allowed_extra = allowed_extra_pairs(manifest, schema)
    known_dupes = known_duplicate_pairs(manifest, schema)

    for pair in sorted(expected - actual):
        status = "expected_missing" if pair in allowed_missing else "unexpected_missing"
        rows.append(
            {
                "artifact": artifact,
                "schema": schema,
                "pair": pair.text(),
                "issue_type": "missing_pair",
                "policy_status": status,
                "cleanup_allowed": "false",
                "evidence": "expected by manifest but absent from filename inventory",
            }
        )
    for pair in sorted(actual - expected):
        status = "allowed_extra" if pair in allowed_extra else "unexpected_extra"
        rows.append(
            {
                "artifact": artifact,
                "schema": schema,
                "pair": pair.text(),
                "issue_type": "extra_pair",
                "policy_status": status,
                "cleanup_allowed": "false",
                "evidence": "present in filename inventory but outside manifest expected range",
            }
        )
    if pair_paths:
        for pair, paths in sorted(pair_paths.items()):
            if len(paths) <= 1:
                continue
            status = "known_duplicate_policy_deferred" if pair in known_dupes else "unexpected_duplicate"
            rows.append(
                {
                    "artifact": artifact,
                    "schema": schema,
                    "pair": pair.text(),
                    "issue_type": "duplicate_pair",
                    "policy_status": status,
                    "cleanup_allowed": "false",
                    "evidence": ";".join(rel(path) for path in paths[:5]),
                }
            )
    return rows


def validate_manifest_markets(manifest: dict[str, Any], alpha_tiered: dict[str, Any]) -> list[str]:
    manifest_markets = [str(item) for item in manifest.get("expected_markets", [])]
    profile = (alpha_tiered.get("profiles") or {}).get("tier_3_research") or {}
    config_markets = [str(item) for item in profile.get("markets", [])]
    if manifest_markets != config_markets:
        return [
            "manifest expected_markets does not match configs/alpha_tiered.yaml::profiles.tier_3_research"
        ]
    return []


def summarize(rows: list[dict[str, str]], manifest: dict[str, Any], coverage_rows: list[dict[str, str]], failures: list[str]) -> str:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(row["artifact"], row["policy_status"])] += 1

    cleanup = manifest.get("artifact_policy", {})
    canonical = manifest.get("canonical_paths", {})
    causal_artifact = str(canonical.get("causal_parquet_pattern", ""))
    exclusions = cleanup.get("exclusions", []) or []
    unknown_paths = [
        item for item in exclusions if str(item.get("classification")) in {"STALE_OR_UNKNOWN", "UNKNOWN"}
    ]
    lines = [
        "# Data Manifest Coverage Summary",
        "",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Verdict",
        "",
        f"- Manifest market cross-check: {'FAIL' if failures else 'PASS'}",
        f"- Cleanup/quarantine allowed: {str(cleanup.get('cleanup_allowed', False)).lower()}",
        f"- Cleanup gate: {cleanup.get('cleanup_gate')}",
        f"- Coverage CSV rows read: {len(coverage_rows)}",
        f"- Issue rows written: {len(rows)}",
        "",
        "## Missing Pairs",
        "",
    ]
    for artifact in [
        "data/raw/{market}/{year}.parquet",
        causal_artifact,
        "data/dbn/status",
    ]:
        expected_count = counts.get((artifact, "expected_missing"), 0)
        unexpected_count = counts.get((artifact, "unexpected_missing"), 0)
        lines.append(f"- `{artifact}`: expected missing {expected_count}; unexpected missing {unexpected_count}.")
    lines.extend(["", "## Extras And Duplicates", ""])
    for artifact in sorted({row["artifact"] for row in rows}):
        allowed_extra = counts.get((artifact, "allowed_extra"), 0)
        unexpected_extra = counts.get((artifact, "unexpected_extra"), 0)
        known_dup = counts.get((artifact, "known_duplicate_policy_deferred"), 0)
        unexpected_dup = counts.get((artifact, "unexpected_duplicate"), 0)
        if allowed_extra or unexpected_extra or known_dup or unexpected_dup:
            lines.append(
                f"- `{artifact}`: allowed extras {allowed_extra}; unexpected extras {unexpected_extra}; "
                f"known policy-deferred duplicates {known_dup}; unexpected duplicates {unexpected_dup}."
            )
    lines.extend(["", "## Cleanup Exclusions", ""])
    for item in exclusions:
        lines.append(
            f"- `{item.get('path')}`: {item.get('classification')} - {item.get('reason')}"
        )
    lines.extend(["", "## UNKNOWN / Policy-Deferred Paths", ""])
    if unknown_paths:
        for item in unknown_paths:
            lines.append(f"- `{item.get('path')}`: {item.get('classification')}")
    else:
        lines.append("- None.")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    lines.extend(
        [
            "",
            "Exact pair-level issues are in `reports/data_manifest/manifest_coverage_check.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "artifact",
        "schema",
        "pair",
        "issue_type",
        "policy_status",
        "cleanup_allowed",
        "evidence",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    canonical = manifest["canonical_paths"]
    dbn_root = ROOT / canonical["dbn_root"]
    expected = expected_pairs(manifest)

    for schema in manifest["schemas"]["dbn"]:
        schema_name = str(schema["name"])
        path_name = str(schema["path_name"])
        actual, pair_paths = dbn_pairs(dbn_root, path_name)
        rows.extend(
            issue_rows_for_artifact(
                artifact=f"data/dbn/{path_name}",
                schema=schema_name,
                expected=expected,
                actual=actual,
                pair_paths=pair_paths,
                manifest=manifest,
            )
        )

    trades = manifest["schemas"]["trades"]
    actual, pair_paths = dbn_pairs(dbn_root, str(trades["path_name"]))
    rows.extend(
        issue_rows_for_artifact(
            artifact=f"data/dbn/{trades['path_name']}",
            schema=str(trades["name"]),
            expected=expected_trade_pairs(manifest),
            actual=actual,
            pair_paths=pair_paths,
            manifest=manifest,
        )
    )

    raw_actual = parquet_pairs(str(canonical["raw_parquet_pattern"]))
    rows.extend(
        issue_rows_for_artifact(
            artifact="data/raw/{market}/{year}.parquet",
            schema="phase1b_raw_parquet",
            expected=expected,
            actual=raw_actual,
            pair_paths=None,
            manifest=manifest,
        )
    )
    causal_actual = parquet_pairs(str(canonical["causal_parquet_pattern"]))
    rows.extend(
        issue_rows_for_artifact(
            artifact=str(canonical["causal_parquet_pattern"]),
            schema="phase2_causal_base_parquet",
            expected=expected,
            actual=causal_actual,
            pair_paths=None,
            manifest=manifest,
        )
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--coverage", default=str(DEFAULT_COVERAGE))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    coverage_path = Path(args.coverage)
    profile_config_path = Path(args.profile_config)
    reports_root = Path(args.reports_root)
    reports_root.mkdir(parents=True, exist_ok=True)

    manifest = read_yaml(manifest_path)
    coverage_rows = read_coverage_csv(coverage_path)
    alpha_tiered = read_yaml(profile_config_path)
    failures = validate_manifest_markets(manifest, alpha_tiered)
    rows = build_rows(manifest)

    csv_path = reports_root / "manifest_coverage_check.csv"
    summary_path = reports_root / "manifest_coverage_summary.md"
    write_csv(csv_path, rows)
    summary_path.write_text(
        summarize(rows, manifest, coverage_rows, failures),
        encoding="utf-8",
    )
    print(
        "manifest_check "
        f"issues={len(rows)} failures={len(failures)} "
        f"csv={csv_path.as_posix()} summary={summary_path.as_posix()}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
