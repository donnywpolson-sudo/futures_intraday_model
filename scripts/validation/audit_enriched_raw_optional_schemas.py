#!/usr/bin/env python3
"""Audit optional status/statistics enrichment in canonical raw parquet files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    STAT_TYPE_FIELDS,
    STATISTICS_ENRICHMENT_COLUMNS,
    STATUS_ENRICHMENT_COLUMNS,
    file_sha256,
    iter_dbn_files,
)


CORE_RAW_COLUMNS = [
    "ts_event",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rtype",
    "publisher_id",
    "instrument_id",
    "symbol",
    "data_quality_status",
    "data_quality_degraded",
    "market",
    "year",
    "raw_symbol",
    "tick_size",
    "contract_multiplier_or_point_value",
    "source_schema",
    "source_dataset",
    "source_file",
    "source_sha256",
]
DEFINITION_COLUMNS = [
    "raw_symbol",
    "tick_size",
    "contract_multiplier_or_point_value",
    "expiration",
    "maturity_year",
    "maturity_month",
]
SOURCE_REF_COLUMNS = [
    ("source_file", "source_sha256"),
    ("status_source_file", "status_source_sha256"),
    *[
        (f"stat_{stat_name}_source_file", f"stat_{stat_name}_source_sha256")
        for stat_name, _ in STAT_TYPE_FIELDS.values()
    ],
]
STATUS_AUDIT_COLUMNS = [
    "status_ts_event",
    "status_source_file",
    "status_source_sha256",
    "status_missing",
    "status_stale",
]
STAT_AUDIT_COLUMNS = [
    column
    for stat_name, _ in STAT_TYPE_FIELDS.values()
    for column in (
        f"stat_{stat_name}_ts_event",
        f"stat_{stat_name}_source_file",
        f"stat_{stat_name}_source_sha256",
        f"stat_{stat_name}_missing",
    )
] + [
    "statistics_missing",
    "statistics_stale",
]
REQUIRED_ENRICHED_COLUMNS = sorted(
    set(CORE_RAW_COLUMNS)
    | set(DEFINITION_COLUMNS)
    | set(STATUS_ENRICHMENT_COLUMNS)
    | set(STATISTICS_ENRICHMENT_COLUMNS)
)
AUDIT_READ_COLUMNS = sorted(
    {
        "ts_event",
        "instrument_id",
        "source_file",
        "source_sha256",
        *STATUS_AUDIT_COLUMNS,
        *STAT_AUDIT_COLUMNS,
    }
)
MAX_SAMPLES = 20


def _raw_index(raw_root: Path) -> dict[tuple[str, int], Path]:
    index: dict[tuple[str, int], Path] = {}
    if not raw_root.exists():
        return index
    for path in sorted(raw_root.glob("*/*.parquet")):
        try:
            year = int(path.stem)
        except ValueError:
            continue
        index[(path.parent.name, year)] = path
    return index


def _schema_index(dbn_root: Path, schema: str) -> set[tuple[str, int]]:
    root = dbn_root / schema
    keys: set[tuple[str, int]] = set()
    if not root.exists():
        return keys
    for path in iter_dbn_files(root):
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            parts = path.parts
        if len(parts) >= 3 and parts[1].isdigit():
            keys.add((parts[0], int(parts[1])))
    return keys


def _resolve_source_path(value: object) -> Path | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.fillna(False).map(lambda value: str(value).strip().lower() in {"true", "1", "yes"})


def _nonnull_text_mask(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype(str).str.strip().ne("")


def _count_true(series: pd.Series) -> int:
    return int(_bool_series(series).sum())


def _failure(message: str, samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"failure": message}
    if samples:
        row["samples"] = samples[:MAX_SAMPLES]
    return row


def _check_source_refs(
    *,
    df: pd.DataFrame,
    available_columns: set[str],
    hash_cache: dict[Path, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    failures: list[dict[str, Any]] = []
    metrics = {
        "source_reference_count": 0,
        "missing_source_file_count": 0,
        "missing_source_hash_count": 0,
        "source_hash_mismatch_count": 0,
    }
    for file_col, hash_col in SOURCE_REF_COLUMNS:
        if file_col not in available_columns or hash_col not in available_columns:
            continue
        refs = df.loc[_nonnull_text_mask(df[file_col]), [file_col, hash_col]].drop_duplicates()
        for _, ref in refs.iterrows():
            source_path = _resolve_source_path(ref[file_col])
            if source_path is None:
                continue
            metrics["source_reference_count"] += 1
            expected_hash = None if pd.isna(ref[hash_col]) else str(ref[hash_col]).strip()
            if not expected_hash:
                metrics["missing_source_hash_count"] += 1
                failures.append(_failure(f"{file_col} has non-null path without {hash_col}", [{"path": str(ref[file_col])}]))
                continue
            if not source_path.is_file():
                metrics["missing_source_file_count"] += 1
                failures.append(_failure(f"{file_col} path does not exist", [{"path": str(ref[file_col])}]))
                continue
            actual_hash = hash_cache.get(source_path)
            if actual_hash is None:
                actual_hash = file_sha256(source_path)
                hash_cache[source_path] = actual_hash
            if actual_hash != expected_hash:
                metrics["source_hash_mismatch_count"] += 1
                failures.append(
                    _failure(
                        f"{file_col}/{hash_col} hash mismatch",
                        [{"path": str(ref[file_col]), "expected": expected_hash, "actual": actual_hash}],
                    )
                )
    return failures, metrics


def _check_status(
    *,
    df: pd.DataFrame,
    key: tuple[str, int],
    status_archive_keys: set[tuple[str, int]],
    available_columns: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    failures: list[dict[str, Any]] = []
    metrics = {
        "status_archive_present": int(key in status_archive_keys),
        "status_missing_rows": 0,
        "status_stale_rows": 0,
        "status_future_timestamp_rows": 0,
        "status_missing_inconsistent_rows": 0,
        "status_stale_inconsistent_rows": 0,
        "missing_status_archive_flag_failure_rows": 0,
    }
    required = {"ts_event", *STATUS_AUDIT_COLUMNS}
    if missing := sorted(required - available_columns):
        failures.append(_failure("status audit columns missing: " + ",".join(missing)))
        return failures, metrics

    ts = pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
    status_ts = pd.to_datetime(df["status_ts_event"], utc=True, errors="coerce")
    status_missing = _bool_series(df["status_missing"])
    status_stale = _bool_series(df["status_stale"])
    metrics["status_missing_rows"] = int(status_missing.sum())
    metrics["status_stale_rows"] = int(status_stale.sum())

    future = status_ts.notna() & ts.notna() & status_ts.gt(ts)
    metrics["status_future_timestamp_rows"] = int(future.sum())
    if future.any():
        failures.append(_failure("status_ts_event is after ts_event", _timestamp_samples(df, future, "status_ts_event")))

    expected_missing = status_ts.isna()
    inconsistent_missing = status_missing.ne(expected_missing)
    metrics["status_missing_inconsistent_rows"] = int(inconsistent_missing.sum())
    if inconsistent_missing.any():
        failures.append(_failure("status_missing is inconsistent with status_ts_event nullness"))

    inconsistent_stale = status_stale.ne(status_missing)
    metrics["status_stale_inconsistent_rows"] = int(inconsistent_stale.sum())
    if inconsistent_stale.any():
        failures.append(_failure("status_stale is inconsistent with status_missing"))

    if key not in status_archive_keys:
        failures.append(_failure("required status DBN archive missing for market-year"))
        source_present = _nonnull_text_mask(df["status_source_file"])
        bad = source_present | status_missing.ne(True) | status_stale.ne(True)
        metrics["missing_status_archive_flag_failure_rows"] = int(bad.sum())
        if bad.any():
            failures.append(_failure("missing status archive is not represented as missing/stale status metadata"))
    return failures, metrics


def _check_statistics(
    *,
    df: pd.DataFrame,
    key: tuple[str, int],
    statistics_archive_keys: set[tuple[str, int]],
    available_columns: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    failures: list[dict[str, Any]] = []
    metrics = {
        "statistics_archive_present": int(key in statistics_archive_keys),
        "statistics_missing_rows": 0,
        "statistics_stale_rows": 0,
        "statistics_future_timestamp_rows": 0,
        "statistics_missing_inconsistent_rows": 0,
        "statistics_stale_inconsistent_rows": 0,
        "missing_statistics_archive_flag_failure_rows": 0,
    }
    required = {"ts_event", *STAT_AUDIT_COLUMNS}
    if missing := sorted(required - available_columns):
        failures.append(_failure("statistics audit columns missing: " + ",".join(missing)))
        return failures, metrics

    ts = pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
    stat_missing_columns: list[str] = []
    future_rows = pd.Series(False, index=df.index)
    inconsistent_rows = pd.Series(False, index=df.index)
    for stat_name, _ in STAT_TYPE_FIELDS.values():
        ts_col = f"stat_{stat_name}_ts_event"
        missing_col = f"stat_{stat_name}_missing"
        stat_missing_columns.append(missing_col)
        stat_ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        future_rows |= stat_ts.notna() & ts.notna() & stat_ts.gt(ts)
        inconsistent_rows |= _bool_series(df[missing_col]).ne(stat_ts.isna())

    metrics["statistics_future_timestamp_rows"] = int(future_rows.sum())
    if future_rows.any():
        failures.append(_failure("one or more stat_*_ts_event values are after ts_event"))

    metrics["statistics_missing_inconsistent_rows"] = int(inconsistent_rows.sum())
    if inconsistent_rows.any():
        failures.append(_failure("one or more stat_*_missing flags are inconsistent with stat timestamp nullness"))

    all_stat_missing = pd.concat([_bool_series(df[col]) for col in stat_missing_columns], axis=1).all(axis=1)
    statistics_missing = _bool_series(df["statistics_missing"])
    statistics_stale = _bool_series(df["statistics_stale"])
    metrics["statistics_missing_rows"] = int(statistics_missing.sum())
    metrics["statistics_stale_rows"] = int(statistics_stale.sum())

    overall_inconsistent = statistics_missing.ne(all_stat_missing)
    if overall_inconsistent.any():
        failures.append(_failure("statistics_missing is inconsistent with all stat_*_missing flags"))

    stale_inconsistent = statistics_stale.ne(statistics_missing)
    metrics["statistics_stale_inconsistent_rows"] = int(stale_inconsistent.sum())
    if stale_inconsistent.any():
        failures.append(_failure("statistics_stale is inconsistent with statistics_missing"))

    if key not in statistics_archive_keys:
        failures.append(_failure("required statistics DBN archive missing for market-year"))
        source_present = pd.Series(False, index=df.index)
        for stat_name, _ in STAT_TYPE_FIELDS.values():
            source_present |= _nonnull_text_mask(df[f"stat_{stat_name}_source_file"])
        bad = source_present | statistics_missing.ne(True) | statistics_stale.ne(True)
        metrics["missing_statistics_archive_flag_failure_rows"] = int(bad.sum())
        if bad.any():
            failures.append(_failure("missing statistics archive is not represented as missing/stale statistics metadata"))
    return failures, metrics


def _timestamp_samples(df: pd.DataFrame, mask: pd.Series, rhs_col: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for _, row in df.loc[mask, ["ts_event", rhs_col, "instrument_id"]].head(MAX_SAMPLES).iterrows():
        samples.append(
            {
                "ts_event": None if pd.isna(row["ts_event"]) else str(row["ts_event"]),
                rhs_col: None if pd.isna(row[rhs_col]) else str(row[rhs_col]),
                "instrument_id": None if pd.isna(row["instrument_id"]) else int(row["instrument_id"]),
            }
        )
    return samples


def _verdict(*, failures: int, warnings: int = 0) -> str:
    if failures:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def build_report(
    *,
    raw_root: Path,
    dbn_root: Path,
    expected_column_count: int | None = 86,
) -> dict[str, Any]:
    raw_files = _raw_index(raw_root)
    status_archive_keys = _schema_index(dbn_root, "status")
    statistics_archive_keys = _schema_index(dbn_root, "statistics")
    hash_cache: dict[Path, str] = {}
    files: list[dict[str, Any]] = []
    schema_signatures: set[tuple[str, ...]] = set()

    totals = {
        "row_count": 0,
        "schema_failure_count": 0,
        "source_hash_mismatch_count": 0,
        "missing_source_file_count": 0,
        "duplicate_key_row_count": 0,
        "status_failure_count": 0,
        "statistics_failure_count": 0,
        "missing_status_archive_market_year_count": 0,
        "missing_statistics_archive_market_year_count": 0,
    }

    for key, path in sorted(raw_files.items()):
        market, year = key
        parquet = pq.ParquetFile(path)
        columns = list(parquet.schema_arrow.names)
        available_columns = set(columns)
        schema_signatures.add(tuple(columns))
        row_count = int(parquet.metadata.num_rows)
        totals["row_count"] += row_count
        failures: list[dict[str, Any]] = []
        warnings: list[str] = []

        missing_required = sorted(set(REQUIRED_ENRICHED_COLUMNS) - available_columns)
        if missing_required:
            failures.append(_failure("missing enriched raw columns: " + ",".join(missing_required)))
        if expected_column_count is not None and len(columns) != expected_column_count:
            failures.append(_failure(f"expected {expected_column_count} columns, found {len(columns)}"))

        read_columns = [column for column in AUDIT_READ_COLUMNS if column in available_columns]
        df = pd.read_parquet(path, columns=read_columns)

        duplicate_count = 0
        if {"ts_event", "instrument_id"}.issubset(df.columns):
            duplicate_count = int(df.duplicated(["ts_event", "instrument_id"]).sum())
            if duplicate_count:
                failures.append(_failure(f"duplicate (ts_event,instrument_id) rows: {duplicate_count}"))
        totals["duplicate_key_row_count"] += duplicate_count

        source_failures, source_metrics = _check_source_refs(
            df=df,
            available_columns=available_columns,
            hash_cache=hash_cache,
        )
        failures.extend(source_failures)

        status_failures, status_metrics = _check_status(
            df=df,
            key=key,
            status_archive_keys=status_archive_keys,
            available_columns=available_columns,
        )
        failures.extend(status_failures)

        statistics_failures, statistics_metrics = _check_statistics(
            df=df,
            key=key,
            statistics_archive_keys=statistics_archive_keys,
            available_columns=available_columns,
        )
        failures.extend(statistics_failures)

        if key not in status_archive_keys:
            warnings.append("missing required status DBN archive for market-year")
            totals["missing_status_archive_market_year_count"] += 1
        if key not in statistics_archive_keys:
            warnings.append("missing required statistics DBN archive for market-year")
            totals["missing_statistics_archive_market_year_count"] += 1

        if missing_required or (expected_column_count is not None and len(columns) != expected_column_count):
            totals["schema_failure_count"] += 1
        totals["source_hash_mismatch_count"] += source_metrics["source_hash_mismatch_count"]
        totals["missing_source_file_count"] += source_metrics["missing_source_file_count"]
        totals["status_failure_count"] += len(status_failures)
        totals["statistics_failure_count"] += len(statistics_failures)

        files.append(
            {
                "market": market,
                "year": year,
                "path": path.as_posix(),
                "rows": row_count,
                "column_count": len(columns),
                "status": "FAIL" if failures else "PASS",
                "warnings": warnings,
                "failures": failures,
                "source_reference_metrics": source_metrics,
                "status_metrics": status_metrics,
                "statistics_metrics": statistics_metrics,
            }
        )

    file_failure_count = sum(1 for row in files if row["status"] == "FAIL")
    status_warning_count = totals["missing_status_archive_market_year_count"]
    statistics_warning_count = totals["missing_statistics_archive_market_year_count"]
    verdicts = {
        "core_raw_readiness": _verdict(
            failures=totals["schema_failure_count"]
            + totals["source_hash_mismatch_count"]
            + totals["missing_source_file_count"]
            + totals["duplicate_key_row_count"]
        ),
        "optional_status_readiness": _verdict(
            failures=totals["status_failure_count"],
            warnings=status_warning_count,
        ),
        "optional_statistics_readiness": _verdict(
            failures=totals["statistics_failure_count"],
            warnings=statistics_warning_count,
        ),
        "alpha_input_readiness": "LIMITED_RESEARCH_INPUT_ONLY",
    }
    return {
        "stage": "raw_enriched_optional_schema_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if file_failure_count else "PASS",
        "raw_root": raw_root.as_posix(),
        "dbn_root": dbn_root.as_posix(),
        "expected_column_count": expected_column_count,
        "file_count": len(files),
        "row_count": totals["row_count"],
        "schema_signature_count": len(schema_signatures),
        "required_enriched_columns": REQUIRED_ENRICHED_COLUMNS,
        "verdicts": verdicts,
        "summary": {
            **totals,
            "file_failure_count": file_failure_count,
            "status_archive_market_year_count": len(status_archive_keys & set(raw_files)),
            "statistics_archive_market_year_count": len(statistics_archive_keys & set(raw_files)),
        },
        "alpha_readiness_caveat": (
            "Raw enriched metadata is available for future research, but direct status_, stat_, "
            "and statistics_ feature use requires a separate leakage-safe feature design."
        ),
        "files": files,
    }


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    verdicts = report["verdicts"]
    lines = [
        "# Enriched Raw Optional Schema Audit",
        "",
        f"- Status: {report['status']}",
        f"- Raw root: `{report['raw_root']}`",
        f"- DBN root: `{report['dbn_root']}`",
        f"- Files: {report['file_count']}",
        f"- Rows: {report['row_count']}",
        f"- Schema signatures: {report['schema_signature_count']}",
        f"- Core raw readiness: {verdicts['core_raw_readiness']}",
        f"- Optional status readiness: {verdicts['optional_status_readiness']}",
        f"- Optional statistics readiness: {verdicts['optional_statistics_readiness']}",
        f"- Alpha input readiness: {verdicts['alpha_input_readiness']}",
        "",
        "## Counts",
        "",
        f"- File failures: {summary['file_failure_count']}",
        f"- Schema failures: {summary['schema_failure_count']}",
        f"- Source hash mismatches: {summary['source_hash_mismatch_count']}",
        f"- Missing source files: {summary['missing_source_file_count']}",
        f"- Duplicate key rows: {summary['duplicate_key_row_count']}",
        f"- Status audit failures: {summary['status_failure_count']}",
        f"- Statistics audit failures: {summary['statistics_failure_count']}",
        f"- Missing optional status archive market-years: {summary['missing_status_archive_market_year_count']}",
        f"- Missing optional statistics archive market-years: {summary['missing_statistics_archive_market_year_count']}",
        "",
        "## Caveat",
        "",
        report["alpha_readiness_caveat"],
        "",
    ]
    failed = [row for row in report["files"] if row["status"] == "FAIL"]
    if failed:
        lines.extend(["## Failed Files", ""])
        for row in failed[:MAX_SAMPLES]:
            failures = "; ".join(str(item["failure"]) for item in row["failures"])
            lines.append(f"- `{row['path']}`: {failures}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--dbn-root", default="data/dbn")
    parser.add_argument("--expected-column-count", type=int, default=86)
    parser.add_argument("--json-out", default="reports/raw_readiness/raw_enriched_optional_schema_audit.json")
    parser.add_argument("--md-out", default="reports/raw_readiness/raw_enriched_optional_schema_audit.md")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        raw_root=Path(args.raw_root),
        dbn_root=Path(args.dbn_root),
        expected_column_count=args.expected_column_count,
    )
    write_json(Path(args.json_out), report)
    if args.md_out:
        write_markdown(Path(args.md_out), report)
    print(
        "status={status} files={file_count} rows={row_count} core={core} "
        "status_optional={status_optional} statistics_optional={statistics_optional} "
        "file_failures={file_failures}".format(
            status=report["status"],
            file_count=report["file_count"],
            row_count=report["row_count"],
            core=report["verdicts"]["core_raw_readiness"],
            status_optional=report["verdicts"]["optional_status_readiness"],
            statistics_optional=report["verdicts"]["optional_statistics_readiness"],
            file_failures=report["summary"]["file_failure_count"],
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
