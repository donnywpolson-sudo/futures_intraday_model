#!/usr/bin/env python3
"""Build a usable/quarantined/diagnostic-only universe from data audit decisions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


USABLE_DECISIONS = {
    "acceptable_with_caveat_ohlcv_empty_minutes_assumed",
    "accept_with_caveat_ohlcv_empty_minutes_assumed",
    "usable_no_synthetic_gaps_detected",
}

QUARANTINE_DECISIONS = {
    "keep_quarantined_ohlcv_only_evidence_insufficient",
    "failed_local_provenance_or_inputs",
    "blocked_missing_or_mismatched_provenance",
}

DIAGNOSTIC_DECISIONS = {
    "diagnostic_only",
    "diagnostic_only_ohlcv_evidence_insufficient",
}


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing decision table: {_relative_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"unreadable decision table {_relative_path(path)}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"decision table must be a JSON object: {_relative_path(path)}"]
    return payload, []


def _read_yaml(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing profile config: {_relative_path(path)}"]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, [f"unreadable profile config {_relative_path(path)}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"profile config must be a YAML mapping: {_relative_path(path)}"]
    return payload, []


def _resolve_profile_name(profile: str, aliases: dict[str, Any]) -> str:
    resolved = profile
    seen: set[str] = set()
    while resolved in aliases and resolved not in seen:
        seen.add(resolved)
        resolved = str(aliases[resolved])
    return resolved


def _load_profile_scope(profile_config: Path, requested_profile: str) -> tuple[dict[str, Any], list[str]]:
    config, failures = _read_yaml(profile_config)
    if failures:
        return {}, failures
    aliases = config.get("aliases", {})
    if not isinstance(aliases, dict):
        aliases = {}
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        return {}, ["profile config missing profiles mapping"]
    resolved = _resolve_profile_name(requested_profile, aliases)
    entry = profiles.get(resolved)
    if not isinstance(entry, dict):
        return {}, [f"profile {requested_profile!r} resolved to {resolved!r} but was not found"]
    markets = [str(item) for item in entry.get("markets", [])]
    years = [int(item) for item in entry.get("years", [])]
    if not markets:
        failures.append(f"profile {resolved!r} has no markets")
    if not years:
        failures.append(f"profile {resolved!r} has no years")
    return {
        "requested_profile": requested_profile,
        "resolved_profile": resolved,
        "markets": markets,
        "years": years,
    }, failures


def _status_for_decision(row: dict[str, Any], diagnostic_markets: set[str]) -> tuple[str, str]:
    decision = str(row.get("final_decision") or "")
    market = str(row.get("market") or "")
    failures = row.get("failures") or []
    if failures:
        return "quarantined", "decision row contains failures"
    if decision in USABLE_DECISIONS:
        return "usable", "decision table marks market-year acceptable under current OHLCV-only evidence"
    if market in diagnostic_markets and decision in QUARANTINE_DECISIONS:
        return "diagnostic_only", "market is explicitly marked diagnostic-only by audit policy"
    if decision in DIAGNOSTIC_DECISIONS:
        return "diagnostic_only", "decision table marks market-year diagnostic-only"
    if decision in QUARANTINE_DECISIONS:
        return "quarantined", "decision table marks market-year quarantined"
    return "quarantined", f"unrecognized final_decision {decision!r}; failed closed"


def build_universe(args: argparse.Namespace) -> dict[str, Any]:
    decision_path = Path(args.decision_table_json)
    profile_config = Path(args.profile_config)
    decision_payload, failures = _read_json(decision_path)
    profile_scope: dict[str, Any] = {
        "requested_profile": None,
        "resolved_profile": None,
        "markets": [],
        "years": [],
    }
    if args.profile:
        profile_scope, profile_failures = _load_profile_scope(profile_config, str(args.profile))
        failures.extend(profile_failures)

    rows = decision_payload.get("rows", [])
    if not isinstance(rows, list):
        failures.append("decision table missing rows list")
        rows = []
    diagnostic_markets = {str(item) for item in (args.diagnostic_only_markets or [])}
    rows_by_pair: dict[tuple[str, int], dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pair = (str(row.get("market") or ""), int(row.get("year") or 0))
        if pair in rows_by_pair:
            duplicates.append(f"{pair[0]} {pair[1]}")
        rows_by_pair[pair] = row
    if duplicates:
        failures.append(f"duplicate decision rows: {', '.join(sorted(duplicates))}")
    if args.profile:
        scope_pairs = {
            (market, int(year))
            for market in profile_scope.get("markets", [])
            for year in profile_scope.get("years", [])
        }
        scope_source = "profile"
    else:
        scope_pairs = set(rows_by_pair)
        scope_source = "decision_table"

    market_years: list[dict[str, Any]] = []
    for market, year in sorted(scope_pairs):
        row = rows_by_pair.get((market, year))
        if row is None:
            market_years.append(
                {
                    "market": market,
                    "year": year,
                    "audit_status": "quarantined",
                    "final_decision": "missing_decision_row",
                    "reason": "missing market-year in decision table; failed closed",
                    "source_reason": None,
                    "missing_minutes": None,
                    "largest_gap_size_minutes": None,
                    "active_session_synthetic_rows": None,
                }
            )
            failures.append(f"missing decision row for {market} {year}")
            continue
        status, reason = _status_for_decision(row, diagnostic_markets)
        market_years.append(
            {
                "market": market,
                "year": year,
                "audit_status": status,
                "final_decision": row.get("final_decision"),
                "reason": reason,
                "source_reason": row.get("reason"),
                "missing_minutes": row.get("missing_minutes"),
                "largest_gap_size_minutes": row.get("largest_gap_size_minutes"),
                "active_session_synthetic_rows": row.get("active_session_synthetic_rows"),
            }
        )

    counts = Counter(str(row["audit_status"]) for row in market_years)
    usable = [row for row in market_years if row["audit_status"] == "usable"]
    quarantined = [row for row in market_years if row["audit_status"] == "quarantined"]
    diagnostic_only = [row for row in market_years if row["audit_status"] == "diagnostic_only"]
    if args.require_usable and not usable:
        failures.append("no usable market-years after applying data audit universe policy")
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "method": "profile-scoped data audit universe derived from market-year decision table",
        "decision_table_json": _relative_path(decision_path),
        "profile": profile_scope,
        "scope_source": scope_source,
        "policy": {
            "usable_decisions": sorted(USABLE_DECISIONS),
            "quarantine_decisions": sorted(QUARANTINE_DECISIONS),
            "diagnostic_decisions": sorted(DIAGNOSTIC_DECISIONS),
            "diagnostic_only_markets": sorted(diagnostic_markets),
            "missing_or_unrecognized_decisions_fail_closed": True,
        },
        "summary": {
            "market_year_count": len(market_years),
            "audit_status_counts": dict(sorted(counts.items())),
            "usable_market_years": [{"market": row["market"], "year": row["year"]} for row in usable],
            "quarantined_market_years": [
                {"market": row["market"], "year": row["year"]} for row in quarantined
            ],
            "diagnostic_only_market_years": [
                {"market": row["market"], "year": row["year"]} for row in diagnostic_only
            ],
        },
        "market_years": market_years,
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = report["summary"]["audit_status_counts"]
    lines = [
        "# Data Audit Universe",
        "",
        f"Generated: {report['generated_at_utc']}",
        f"Status: `{report['status']}`",
        f"Decision table: `{report['decision_table_json']}`",
        f"Profile: `{report['profile'].get('resolved_profile')}`",
        "",
        "Status counts: "
        + ", ".join(f"`{key}`={value}" for key, value in sorted(counts.items())),
        "",
        "| Market | Year | Audit status | Final decision | Missing min | Largest gap | Active synthetic | Reason |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for row in report["market_years"]:
        lines.append(
            "| `{market}` | {year} | `{status}` | `{decision}` | {missing} | {gap} | {active} | {reason} |".format(
                market=row["market"],
                year=row["year"],
                status=row["audit_status"],
                decision=row["final_decision"],
                missing="" if row["missing_minutes"] is None else row["missing_minutes"],
                gap="" if row["largest_gap_size_minutes"] is None else row["largest_gap_size_minutes"],
                active=""
                if row["active_session_synthetic_rows"] is None
                else row["active_session_synthetic_rows"],
                reason=row["reason"],
            )
        )
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in report["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-table-json", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--profile-config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--diagnostic-only-markets", nargs="*", default=[])
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--require-usable", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_universe(args)
    write_json_report(report, Path(args.json_out))
    if args.md_out:
        write_markdown_report(report, Path(args.md_out))
    if report["status"] != "PASS":
        print(f"FAIL data audit universe: failures={len(report['failures'])}")
        return 1
    print(
        "PASS data audit universe: "
        f"market_years={report['summary']['market_year_count']} "
        f"statuses={report['summary']['audit_status_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
