#!/usr/bin/env python3
"""Audit whether local SR1/SR3 DBNs can support explicit roll-chain repair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_DBN_ROOT = Path("data/dbn")
DEFAULT_MARKETS = ("SR1", "SR3")
DEFAULT_YEARS = tuple(range(2018, 2027))
REQUIRED_SCHEMAS = ("ohlcv_1m", "definition", "status", "statistics")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dbn-root", default=str(DEFAULT_DBN_ROOT))
    parser.add_argument(
        "--sidecar-dbn-root",
        default=None,
        help="Root for definition/status/statistics DBNs. Defaults to --dbn-root.",
    )
    parser.add_argument("--definition-dbn-root", default=None)
    parser.add_argument("--status-dbn-root", default=None)
    parser.add_argument("--statistics-dbn-root", default=None)
    parser.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--json-out")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_paths(dbn_root: Path, schema: str, market: str, year: int) -> list[Path]:
    roots = [
        dbn_root / schema / market / str(year),
        dbn_root / market / str(year),
    ]
    for root in roots:
        if root.exists():
            return sorted(root.glob("*.dbn.zst.manifest.json"))
    return []


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"manifest unreadable: {path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return None, f"manifest is not a JSON object: {path.as_posix()}"
    return payload, None


def _dbn_path_for_manifest(path: Path) -> Path:
    name = path.name.removesuffix(".manifest.json")
    return path.with_name(name)


def _manifest_file_failures(path: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    dbn_path = _dbn_path_for_manifest(path)
    if not dbn_path.exists():
        failures.append(f"missing DBN file for manifest: {dbn_path.as_posix()}")
        return failures
    expected_hash = str(manifest.get("file_sha256") or "")
    if expected_hash:
        actual_hash = _sha256(dbn_path)
        if actual_hash != expected_hash:
            failures.append(
                f"DBN hash mismatch for {dbn_path.as_posix()}: "
                f"expected {expected_hash} actual {actual_hash}"
            )
    if str(manifest.get("request_status") or "ok") != "ok":
        failures.append(
            f"manifest request_status is not ok: {path.as_posix()} "
            f"status={manifest.get('request_status')}"
        )
    return failures


def _schema_summary(
    dbn_root: Path,
    schema: str,
    market: str,
    year: int,
) -> dict[str, Any]:
    paths = _manifest_paths(dbn_root, schema, market, year)
    manifests: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in paths:
        manifest, error = _load_manifest(path)
        if error:
            failures.append(error)
            continue
        assert manifest is not None
        manifests.append(manifest)
        failures.extend(_manifest_file_failures(path, manifest))

    return {
        "schema": schema,
        "dbn_root": dbn_root.as_posix(),
        "manifest_count": len(paths),
        "manifest_paths": [path.as_posix() for path in paths],
        "schemas": sorted({str(item.get("schema")) for item in manifests}),
        "stype_in_values": sorted({str(item.get("stype_in")) for item in manifests}),
        "symbols_requested": sorted(
            {
                str(symbol)
                for item in manifests
                for symbol in (item.get("symbols_requested") or [])
            }
        ),
        "failures": failures,
    }


def _has_parent_or_explicit_source(summary: dict[str, Any], market: str) -> bool:
    stypes = {str(value).lower() for value in summary["stype_in_values"]}
    symbols = set(summary["symbols_requested"])
    if "parent" in stypes and f"{market}.FUT" in symbols:
        return True
    return bool(stypes.intersection({"raw_symbol", "instrument_id"}))


def _schema_roots(
    *,
    dbn_root: Path,
    sidecar_dbn_root: Path | None,
    definition_dbn_root: Path | None,
    status_dbn_root: Path | None,
    statistics_dbn_root: Path | None,
) -> dict[str, Path]:
    effective_sidecar_root = sidecar_dbn_root or dbn_root
    return {
        "ohlcv_1m": dbn_root,
        "definition": definition_dbn_root or effective_sidecar_root,
        "status": status_dbn_root or effective_sidecar_root,
        "statistics": statistics_dbn_root or effective_sidecar_root,
    }


def audit_market_year(
    dbn_root: Path,
    market: str,
    year: int,
    *,
    sidecar_dbn_root: Path | None = None,
    definition_dbn_root: Path | None = None,
    status_dbn_root: Path | None = None,
    statistics_dbn_root: Path | None = None,
) -> dict[str, Any]:
    roots = _schema_roots(
        dbn_root=dbn_root,
        sidecar_dbn_root=sidecar_dbn_root,
        definition_dbn_root=definition_dbn_root,
        status_dbn_root=status_dbn_root,
        statistics_dbn_root=statistics_dbn_root,
    )
    schemas = {
        schema: _schema_summary(
            roots[schema],
            schema,
            market,
            year,
        )
        for schema in REQUIRED_SCHEMAS
    }
    blockers: list[str] = []
    for schema, summary in schemas.items():
        if summary["manifest_count"] == 0:
            blockers.append(f"missing {schema} DBN manifest")
        blockers.extend(summary["failures"])

    ohlcv = schemas["ohlcv_1m"]
    if ohlcv["manifest_count"] and not _has_parent_or_explicit_source(ohlcv, market):
        blockers.append(
            "ohlcv_1m DBN is continuous-only; explicit monotonic roll repair "
            "requires parent or explicit-contract OHLCV DBN"
        )
    for schema in ("definition", "status", "statistics"):
        summary = schemas[schema]
        if summary["manifest_count"] and not _has_parent_or_explicit_source(summary, market):
            blockers.append(
                f"{schema} DBN is continuous-only; explicit monotonic roll repair "
                f"requires parent or explicit-contract {schema} DBN"
            )

    return {
        "market": market,
        "year": year,
        "status": "PASS" if not blockers else "FAIL",
        "repair_source_ready": not blockers,
        "blockers": blockers,
        "schemas": schemas,
    }


def build_report(
    *,
    dbn_root: Path,
    sidecar_dbn_root: Path | None = None,
    definition_dbn_root: Path | None = None,
    status_dbn_root: Path | None = None,
    statistics_dbn_root: Path | None = None,
    markets: list[str],
    years: list[int],
) -> dict[str, Any]:
    roots = _schema_roots(
        dbn_root=dbn_root,
        sidecar_dbn_root=sidecar_dbn_root,
        definition_dbn_root=definition_dbn_root,
        status_dbn_root=status_dbn_root,
        statistics_dbn_root=statistics_dbn_root,
    )
    rows = [
        audit_market_year(
            dbn_root,
            market,
            year,
            sidecar_dbn_root=sidecar_dbn_root,
            definition_dbn_root=definition_dbn_root,
            status_dbn_root=status_dbn_root,
            statistics_dbn_root=statistics_dbn_root,
        )
        for market in markets
        for year in years
    ]
    blocked = [row for row in rows if row["status"] != "PASS"]
    return {
        "stage": "sr_roll_repair_source_audit",
        "status": "PASS" if not blocked else "FAIL",
        "policy": {
            "canonical_raw_overwrite": False,
            "required_ohlcv_source": "parent_or_explicit_contract_not_continuous",
            "required_sidecar_source": "parent_or_explicit_contract_not_continuous",
            "required_sidecars": ["definition", "status", "statistics"],
        },
        "dbn_root": dbn_root.as_posix(),
        "sidecar_dbn_root": (sidecar_dbn_root or dbn_root).as_posix(),
        "definition_dbn_root": roots["definition"].as_posix(),
        "status_dbn_root": roots["status"].as_posix(),
        "statistics_dbn_root": roots["statistics"].as_posix(),
        "market_count": len(markets),
        "year_count": len(years),
        "market_year_count": len(rows),
        "repair_source_ready_count": len(rows) - len(blocked),
        "blocked_count": len(blocked),
        "rows": rows,
        "next_action": (
            "Use parent/explicit-contract OHLCV DBN in a separate candidate root before "
            "rewriting SR1/SR3 raw data."
            if blocked
            else "Build SR1/SR3 repaired raw candidate from explicit roll-chain DBNs."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_report(
        dbn_root=Path(args.dbn_root),
        sidecar_dbn_root=Path(args.sidecar_dbn_root) if args.sidecar_dbn_root else None,
        definition_dbn_root=Path(args.definition_dbn_root) if args.definition_dbn_root else None,
        status_dbn_root=Path(args.status_dbn_root) if args.status_dbn_root else None,
        statistics_dbn_root=(
            Path(args.statistics_dbn_root) if args.statistics_dbn_root else None
        ),
        markets=[str(market) for market in args.markets],
        years=[int(year) for year in args.years],
    )
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"{report['status']} SR roll repair source audit: "
        f"ready={report['repair_source_ready_count']} blocked={report['blocked_count']}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
