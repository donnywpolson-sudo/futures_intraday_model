#!/usr/bin/env python3
"""Console-only inventory for local optional status/statistics DBN archives."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    raw_file_manifest_path,
    validate_raw_file_manifest,
)


STAGE = "local_trade_optional_archive_inventory"
STATUS_READY = "REVIEW_READY_LOCAL_TRADE_OPTIONAL_ARCHIVE_INVENTORY"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_OPTIONAL_ARCHIVE_INVENTORY"

DEFAULT_DBN_ROOT = Path("data/dbn")
DEFAULT_YEAR = 2026
DEFAULT_START = "2026-01-01"
DEFAULT_END = "2026-06-13"
DEFAULT_SCHEMAS = ("statistics", "status")
DEFAULT_EXPECTED_MARKET_COUNT = 33

FALSE_APPROVAL_FLAGS = (
    "provider_download_approved",
    "candidate_raw_write_approved",
    "readiness_rerun_approved",
    "causal_base_repair_approved",
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "proof_scan_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)


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


def _approval_flags() -> dict[str, bool]:
    return {flag: False for flag in FALSE_APPROVAL_FLAGS}


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _read_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    manifest_path = raw_file_manifest_path(path)
    if not manifest_path.exists():
        return {}, [f"missing manifest: {manifest_path.as_posix()}"]
    if manifest_path.stat().st_size <= 0:
        return {}, [f"empty manifest: {manifest_path.as_posix()}"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - runtime detail is the useful part.
        return {}, [f"unreadable manifest: {type(exc).__name__}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"manifest is not a JSON object: {manifest_path.as_posix()}"]
    return payload, []


def _archive_path(dbn_root: Path, *, schema: str, market: str, year: int, start: str, end: str) -> Path:
    return dbn_root / schema / market / str(year) / f"{start}_{end}.dbn.zst"


def _discover_markets(dbn_root: Path, schemas: Iterable[str]) -> list[str]:
    markets: set[str] = set()
    for schema in schemas:
        schema_root = dbn_root / schema
        if not schema_root.is_dir():
            continue
        markets.update(path.name for path in schema_root.iterdir() if path.is_dir())
    return sorted(markets)


def _archive_item(
    *,
    repo_root: Path,
    dbn_root: Path,
    schema: str,
    market: str,
    year: int,
    start: str,
    end: str,
) -> dict[str, Any]:
    path = _archive_path(dbn_root, schema=schema, market=market, year=year, start=start, end=end)
    manifest_path = raw_file_manifest_path(path)
    failures: list[str] = []
    if not path.exists():
        failures.append("archive missing")
    elif path.stat().st_size <= 0:
        failures.append("archive empty")

    manifest, manifest_read_failures = _read_manifest(path)
    failures.extend(manifest_read_failures)
    if path.exists() and path.stat().st_size > 0 and manifest and not manifest_read_failures:
        manifest_failures = validate_raw_file_manifest(
            path,
            expected_schema=schema,
            expected_market=market,
            expected_year=year,
        )
        if "manifest path mismatch" in manifest_failures and manifest.get("path") == rel(path, repo_root):
            manifest_failures.remove("manifest path mismatch")
        failures.extend(manifest_failures)
        if manifest.get("start") != start:
            failures.append("manifest start mismatch")
        if manifest.get("end") != end:
            failures.append("manifest end mismatch")

    return {
        "schema": schema,
        "market": market,
        "year": year,
        "start": start,
        "end": end,
        "archive_path": rel(path, repo_root),
        "manifest_path": rel(manifest_path, repo_root),
        "archive_present": path.exists(),
        "archive_size_bytes": path.stat().st_size if path.exists() else 0,
        "manifest_present": manifest_path.exists(),
        "manifest_size_bytes": manifest_path.stat().st_size if manifest_path.exists() else 0,
        "manifest_request_status": manifest.get("request_status"),
        "failures": failures,
        "status": "FAIL" if failures else "PASS",
    }


def build_report(
    *,
    repo_root: Path,
    dbn_root: Path,
    markets: list[str] | None = None,
    schemas: tuple[str, ...] = DEFAULT_SCHEMAS,
    year: int = DEFAULT_YEAR,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    expected_market_count: int | None = DEFAULT_EXPECTED_MARKET_COUNT,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    selected_markets = sorted(markets if markets is not None else _discover_markets(dbn_root, schemas))
    archive_items = [
        _archive_item(
            repo_root=repo_root,
            dbn_root=dbn_root,
            schema=schema,
            market=market,
            year=year,
            start=start,
            end=end,
        )
        for market in selected_markets
        for schema in schemas
    ]
    by_market: dict[str, dict[str, Any]] = {}
    for market in selected_markets:
        market_items = [item for item in archive_items if item["market"] == market]
        by_market[market] = {
            "status": "PASS" if all(item["status"] == "PASS" for item in market_items) else "FAIL",
            "archives": market_items,
        }

    staged_paths = sorted(staged_generated_paths) if staged_generated_paths is not None else _git_staged_generated_paths(repo_root)
    invalid_items = [item for item in archive_items if item["status"] != "PASS"]
    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="expected_market_count_met",
        passed=expected_market_count is None or len(selected_markets) == expected_market_count,
        observed=len(selected_markets),
        expected=expected_market_count,
        detail="The optional archive inventory should cover the expected futures market universe.",
    )
    _check(
        checks,
        name="optional_archive_manifests_valid",
        passed=not invalid_items,
        observed=[
            {
                "market": item["market"],
                "schema": item["schema"],
                "failures": item["failures"],
            }
            for item in invalid_items
        ],
        expected=[],
        detail="Every selected market/schema must have a non-empty archive with an exact-window valid manifest.",
    )
    _check(
        checks,
        name="staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged during inventory.",
    )
    _check(
        checks,
        name="console_only_default",
        passed=True,
        observed="no output writer",
        expected="console-only",
        detail="This gate has no report output arguments and does not write generated artifacts.",
    )
    failures = [check for check in checks if check["status"] == "FAIL"]
    ready_markets = [market for market, row in by_market.items() if row["status"] == "PASS"]

    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": STATUS_NO_GO if failures else STATUS_READY,
            "year": year,
            "start": start,
            "end": end,
            "schemas": list(schemas),
            "market_count": len(selected_markets),
            "expected_market_count": expected_market_count,
            "archive_count": len(archive_items),
            "ready_market_count": len(ready_markets),
            "invalid_market_count": len(selected_markets) - len(ready_markets),
            "invalid_archive_count": len(invalid_items),
            "generated_output_count": 0,
            "staged_generated_path_count": len(staged_paths),
            "failure_count": len(failures),
            "recommended_next_action": (
                "Use this local optional archive evidence in the ES 2026 v2 dry-run/availability gates; "
                "do not download providers or write candidate raw without separate approval."
            ),
            **_approval_flags(),
        },
        "checks": checks,
        "markets": selected_markets,
        "ready_markets": ready_markets,
        "invalid_markets": [market for market, row in by_market.items() if row["status"] != "PASS"],
        "by_market": by_market,
        "non_approval": {
            "scope": "local optional status/statistics archive inventory only",
            "generated_report_written": False,
            "generated_output_count": 0,
            **_approval_flags(),
        },
    }


def _parse_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return sorted(item.strip() for item in value.split(",") if item.strip())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dbn-root", default=str(DEFAULT_DBN_ROOT))
    parser.add_argument("--markets", default=None, help="Comma-separated markets. Defaults to schema directory union.")
    parser.add_argument("--schemas", default=",".join(DEFAULT_SCHEMAS))
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--expected-market-count", type=int, default=DEFAULT_EXPECTED_MARKET_COUNT)
    parser.add_argument("--json", action="store_true", help="Print full JSON report to stdout.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    schemas = tuple(_parse_csv(args.schemas) or [])
    report = build_report(
        repo_root=repo_root,
        dbn_root=resolve_path(repo_root, args.dbn_root),
        markets=_parse_csv(args.markets),
        schemas=schemas,
        year=args.year,
        start=args.start,
        end=args.end,
        expected_market_count=args.expected_market_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            f"{STAGE} status={summary['status']} "
            f"markets={summary['market_count']} "
            f"ready_markets={summary['ready_market_count']} "
            f"invalid_markets={summary['invalid_market_count']} "
            f"archives={summary['archive_count']} "
            f"invalid_archives={summary['invalid_archive_count']} "
            f"generated_outputs={summary['generated_output_count']} "
            f"staged_generated_paths={summary['staged_generated_path_count']} "
            f"failure_count={summary['failure_count']}"
        )
    return 0 if report["summary"]["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
