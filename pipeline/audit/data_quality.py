from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows


REQUIRED = ["ts_event", "open", "high", "low", "close", "volume"]


def audit_file(path: Path) -> dict[str, Any]:
    row = {"file": str(path), "market": path.parent.name, "year": path.stem, "status": "PASS"}
    issues: list[str] = []
    try:
        lf = pl.scan_parquet(path)
        cols = lf.collect_schema().names()
        row["schema"] = cols
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            issues.append(f"missing_required_columns={missing}")
            row["status"] = "FAIL"
        exprs = [pl.len().alias("row_count")]
        if "ts_event" in cols:
            exprs += [
                pl.col("ts_event").min().alias("first_ts"),
                pl.col("ts_event").max().alias("last_ts"),
                pl.col("ts_event").null_count().alias("null_timestamps"),
                (pl.col("ts_event").diff() < 0).sum().alias("non_monotonic_steps"),
                pl.col("ts_event").n_unique().alias("unique_timestamps"),
            ]
        for c in ["open", "high", "low", "close"]:
            if c in cols:
                exprs.append(pl.col(c).null_count().alias(f"null_{c}"))
                exprs.append((pl.col(c) <= 0).sum().alias(f"nonpositive_{c}"))
        if "volume" in cols:
            exprs.append((pl.col("volume") < 0).sum().alias("negative_volume"))
        if {"high", "low"}.issubset(cols):
            exprs.append((pl.col("high") < pl.col("low")).sum().alias("high_lt_low"))
        if {"open", "high", "low"}.issubset(cols):
            exprs.append(((pl.col("open") > pl.col("high")) | (pl.col("open") < pl.col("low"))).sum().alias("open_outside_hilo"))
        if {"close", "high", "low"}.issubset(cols):
            exprs.append(((pl.col("close") > pl.col("high")) | (pl.col("close") < pl.col("low"))).sum().alias("close_outside_hilo"))
        metrics = lf.select(exprs).collect().row(0, named=True)
        row.update(metrics)
        for k, v in metrics.items():
            if k.startswith(("null_", "nonpositive_", "negative_", "high_lt", "open_outside", "close_outside", "non_monotonic")) and v:
                issues.append(f"{k}={v}")
        if metrics.get("unique_timestamps") is not None and metrics.get("row_count") != metrics.get("unique_timestamps"):
            issues.append("duplicate_timestamps")
        if issues and row["status"] != "FAIL":
            row["status"] = "WARN"
    except Exception as exc:
        row["status"] = "FAIL"
        issues.append(f"read_error={exc}")
    row["issues"] = issues
    return row


def run_data_quality_audit(root: str | Path, out: str | Path, fail_fast: bool = False) -> dict[str, Any]:
    root = Path(root)
    rows = []
    for path in sorted(root.glob("*/*.parquet")):
        row = audit_file(path)
        rows.append(row)
        if fail_fast and row["status"] == "FAIL":
            break
    status = "FAIL" if any(r["status"] == "FAIL" for r in rows) else ("WARN" if any(r["status"] == "WARN" for r in rows) else "PASS")
    report = {"status": status, "root": str(root), "files": rows}
    atomic_write_json(out, report)
    write_csv_rows(Path(out).with_suffix(".csv"), [{k: v for k, v in r.items() if k not in {"schema", "issues"}} for r in rows])
    if fail_fast and status == "FAIL":
        raise SystemExit(f"data quality audit failed: {out}")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fail-fast", action="store_true")
    args = p.parse_args()
    report = run_data_quality_audit(args.root, args.out, args.fail_fast)
    print(report["status"])


if __name__ == "__main__":
    main()
