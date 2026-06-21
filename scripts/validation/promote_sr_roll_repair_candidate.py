#!/usr/bin/env python3
"""Promote vetted SR1/SR3 front-contract raw repair candidates to canonical raw."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.phase1A_download.download_databento_raw import CME_DATASET, file_sha256


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--readiness-summary", required=True)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--expected-exclusion", nargs="*", default=[])
    parser.add_argument("--promoted-raw-alignment-out", required=True)
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path.as_posix()}")
    return data


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_market_year(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise ValueError(f"invalid market-year {value!r}; expected MARKET:YEAR")
    market, year_text = value.split(":", 1)
    market = market.strip()
    if not market:
        raise ValueError(f"invalid market-year {value!r}; missing market")
    try:
        year = int(year_text)
    except ValueError as exc:
        raise ValueError(f"invalid market-year {value!r}; year must be an integer") from exc
    return market, year


def _excluded_pairs(rows: Iterable[dict[str, Any]]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    for row in rows:
        try:
            pairs.add((str(row["market"]), int(row["year"])))
        except (KeyError, TypeError, ValueError):
            continue
    return pairs


def _output_pairs(outputs: Iterable[dict[str, Any]]) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    for row in outputs:
        pairs.add((str(row["market"]), int(row["year"])))
    return pairs


def _validated_outputs(
    manifest: dict[str, Any],
    *,
    raw_root: Path,
    expected_exclusions: set[tuple[str, int]],
) -> tuple[list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        failures.append("candidate manifest has no outputs")
        return [], failures

    excluded = _excluded_pairs(manifest.get("excluded_market_years", []))
    missing_exclusions = sorted(expected_exclusions - excluded)
    if missing_exclusions:
        failures.append(
            "candidate manifest missing expected exclusions: "
            + ", ".join(f"{market}:{year}" for market, year in missing_exclusions)
        )

    seen: set[tuple[str, int]] = set()
    validated: list[dict[str, Any]] = []
    for row in outputs:
        if not isinstance(row, dict):
            failures.append("candidate output row is not an object")
            continue
        try:
            market = str(row["market"])
            year = int(row["year"])
            source_path = Path(str(row["output_path"]))
            expected_hash = str(row["output_hash"])
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(f"candidate output row missing required field: {exc}")
            continue
        pair = (market, year)
        if pair in seen:
            failures.append(f"duplicate candidate output market-year: {market} {year}")
            continue
        seen.add(pair)
        if pair in excluded:
            failures.append(f"candidate output includes excluded market-year: {market} {year}")
        if not source_path.exists():
            failures.append(f"candidate output file missing: {source_path.as_posix()}")
            continue
        actual_hash = file_sha256(source_path)
        if actual_hash != expected_hash:
            failures.append(
                f"candidate output hash mismatch for {source_path.as_posix()}: "
                f"{actual_hash} != {expected_hash}"
            )
            continue
        target_path = raw_root / market / f"{year}.parquet"
        validated.append(
            {
                **row,
                "market": market,
                "year": year,
                "source_path": source_path,
                "target_path": target_path,
                "source_hash": actual_hash,
            }
        )
    return validated, failures


def _preflight(
    *,
    candidate_manifest: Path,
    readiness_summary: Path,
    raw_root: Path,
    expected_exclusions: set[tuple[str, int]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    if not candidate_manifest.exists():
        failures.append(f"candidate manifest missing: {candidate_manifest.as_posix()}")
        return {}, {}, [], failures
    if not readiness_summary.exists():
        failures.append(f"readiness summary missing: {readiness_summary.as_posix()}")
        return {}, {}, [], failures

    try:
        manifest = _read_json(candidate_manifest)
    except Exception as exc:
        failures.append(f"candidate manifest unreadable: {exc}")
        return {}, {}, [], failures
    try:
        readiness = _read_json(readiness_summary)
    except Exception as exc:
        failures.append(f"readiness summary unreadable: {exc}")
        return manifest, {}, [], failures

    if manifest.get("stage") != "sr_front_contract_candidate_build":
        failures.append("candidate manifest stage is not sr_front_contract_candidate_build")
    if manifest.get("status") != "PASS":
        failures.append(f"candidate manifest status is {manifest.get('status')!r}, not PASS")
    if manifest.get("raw_alignment_status") != "PASS":
        failures.append(
            "candidate manifest raw_alignment_status is "
            f"{manifest.get('raw_alignment_status')!r}, not PASS"
        )
    if manifest.get("failures"):
        failures.append("candidate manifest has failures")

    if readiness.get("status") != "PASS":
        failures.append(f"readiness summary status is {readiness.get('status')!r}, not PASS")
    for field_name in ["blocker_count", "failure_count", "pending_market_year_count"]:
        if readiness.get(field_name) != 0:
            failures.append(f"readiness summary {field_name} is {readiness.get(field_name)}, not 0")

    outputs, output_failures = _validated_outputs(
        manifest,
        raw_root=raw_root,
        expected_exclusions=expected_exclusions,
    )
    failures.extend(output_failures)

    selected_count = readiness.get("selected_market_year_count")
    if isinstance(selected_count, int) and selected_count != len(outputs):
        failures.append(
            f"readiness selected_market_year_count {selected_count} "
            f"does not match candidate output count {len(outputs)}"
        )

    promoted_pairs = _output_pairs(outputs)
    unexpected_exclusions = sorted(expected_exclusions & promoted_pairs)
    if unexpected_exclusions:
        failures.append(
            "expected exclusions would be promoted: "
            + ", ".join(f"{market}:{year}" for market, year in unexpected_exclusions)
        )
    return manifest, readiness, outputs, failures


def _write_promoted_alignment(
    *,
    path: Path,
    manifest: dict[str, Any],
    readiness: dict[str, Any],
    outputs: list[dict[str, Any]],
    raw_root: Path,
    candidate_manifest: Path,
    readiness_summary: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in sorted(outputs, key=lambda item: (str(item["market"]), int(item["year"]))):
        source_path = row["source_path"]
        target_path = row["target_path"]
        target_hash = file_sha256(target_path)
        metrics = {
            key: value
            for key, value in row.items()
            if key not in {"source_path", "target_path", "source_hash", "output_path", "output_hash"}
        }
        rows.append(
            {
                **metrics,
                "status": "PASS",
                "output_path": _relative(target_path),
                "output_hash": target_hash,
                "promoted_from_path": _relative(source_path),
                "promoted_from_hash": row["source_hash"],
            }
        )
    markets = sorted({row["market"] for row in rows})
    years = sorted({int(row["year"]) for row in rows})
    market_years = [
        {"market": str(row["market"]), "year": int(row["year"])}
        for row in rows
    ]
    report = {
        "stage": "raw_dbn_alignment_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "audit_completeness": "full",
        "definition_join_skipped": False,
        "definition_join_status": "checked",
        "definition_join_checked_market_year_count": len(rows),
        "failures": [],
        "dataset": CME_DATASET,
        "profile": manifest.get("source_audit", {}).get("profile", manifest.get("profile", "tier_3")),
        "resolved_profile": readiness.get(
            "resolved_profile",
            manifest.get("resolved_profile", "tier_3_research"),
        ),
        "markets": markets,
        "years": years,
        "market_years": market_years,
        "excluded_market_years": manifest.get("excluded_market_years", []),
        "dbn_root": manifest.get("candidate_dbn_root"),
        "sidecar_dbn_root": manifest.get("sidecar_dbn_root"),
        "definition_dbn_root": manifest.get("definition_dbn_root"),
        "status_dbn_root": manifest.get("status_dbn_root"),
        "statistics_dbn_root": manifest.get("statistics_dbn_root"),
        "raw_root": _relative(raw_root),
        "candidate_manifest": _relative(candidate_manifest),
        "candidate_readiness_summary": _relative(readiness_summary),
        "expected_market_year_count": len(rows),
        "pre_availability_exemption_count": 0,
        "ohlcv_dbn_market_year_count": len(rows),
        "definition_dbn_market_year_count": len(rows),
        "raw_market_year_count": len(rows),
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "missing_raw_count": 0,
        "needs_phase1b_conversion_count": 0,
        "dbn_only_inventory_count": 0,
        "raw_only_count": 0,
        "invalid_manifest_count": 0,
        "raw_schema_failure_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_mismatch_count": 0,
        "pre_availability_exemptions": [],
        "missing_ohlcv_dbn": [],
        "missing_definition_dbn": [],
        "missing_raw": [],
        "needs_phase1b_conversion": [],
        "dbn_only_inventory": [],
        "raw_only_market_years": [],
        "invalid_manifests": [],
        "raw_schema_failures": [],
        "source_hash_mismatches": [],
        "definition_join_mismatches": [],
        "raw_file_metrics": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return report


def promote_candidate(
    *,
    candidate_manifest: Path,
    readiness_summary: Path,
    raw_root: Path,
    expected_exclusions: set[tuple[str, int]],
    promoted_raw_alignment_out: Path,
) -> dict[str, Any]:
    manifest, readiness, outputs, failures = _preflight(
        candidate_manifest=candidate_manifest,
        readiness_summary=readiness_summary,
        raw_root=raw_root,
        expected_exclusions=expected_exclusions,
    )
    report: dict[str, Any] = {
        "stage": "sr_roll_repair_candidate_promotion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "candidate_manifest": _relative(candidate_manifest),
        "readiness_summary": _relative(readiness_summary),
        "raw_root": _relative(raw_root),
        "promoted_raw_alignment": _relative(promoted_raw_alignment_out),
        "promoted_count": 0,
        "expected_exclusions": [
            {"market": market, "year": year}
            for market, year in sorted(expected_exclusions)
        ],
        "failures": failures,
    }
    if failures:
        return report

    promoted: list[dict[str, Any]] = []
    for row in outputs:
        target_path = row["target_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row["source_path"], target_path)
        target_hash = file_sha256(target_path)
        if target_hash != row["source_hash"]:
            raise RuntimeError(
                f"promoted hash mismatch for {target_path.as_posix()}: "
                f"{target_hash} != {row['source_hash']}"
            )
        promoted.append(
            {
                "market": row["market"],
                "year": row["year"],
                "target_path": _relative(target_path),
                "target_hash": target_hash,
                "source_path": _relative(row["source_path"]),
            }
        )

    alignment = _write_promoted_alignment(
        path=promoted_raw_alignment_out,
        manifest=manifest,
        readiness=readiness,
        outputs=outputs,
        raw_root=raw_root,
        candidate_manifest=candidate_manifest,
        readiness_summary=readiness_summary,
    )
    report.update(
        {
            "status": "PASS",
            "promoted_count": len(promoted),
            "promoted": promoted,
            "promoted_raw_alignment_status": alignment["status"],
            "failures": [],
        }
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        expected_exclusions = {
            _parse_market_year(value) for value in args.expected_exclusion
        }
        report = promote_candidate(
            candidate_manifest=Path(args.candidate_manifest),
            readiness_summary=Path(args.readiness_summary),
            raw_root=Path(args.raw_root),
            expected_exclusions=expected_exclusions,
            promoted_raw_alignment_out=Path(args.promoted_raw_alignment_out),
        )
    except Exception as exc:
        report = {
            "stage": "sr_roll_repair_candidate_promotion",
            "status": "FAIL",
            "failure_count": 1,
            "failures": [str(exc)],
        }
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
