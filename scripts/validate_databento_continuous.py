from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.data_gate.manifest import build_data_manifest


REQUIRED = ["ts_event", "open", "high", "low", "close", "volume"]
CANONICAL_VALIDATED_SCHEMA = {
    "ts_event": pl.Datetime("ns", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


def canonicalize_validated_df(df: pl.DataFrame) -> pl.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    return df.select([pl.col(c).cast(dtype).alias(c) for c, dtype in CANONICAL_VALIDATED_SCHEMA.items()])


def validate_raw_to_validated(
    raw_root: str | Path = "data/raw",
    validated_root: str | Path = "data/validated",
    *,
    write_validated: bool = False,
    clean_policy: str = "drop-invalid",
    markets: list[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    raw_root = Path(raw_root)
    validated_root = Path(validated_root)
    market_set = set(markets or [])
    rows = []
    failures = []
    for p in sorted(raw_root.glob("*/*.parquet")):
        if market_set and p.parent.name not in market_set:
            continue
        try:
            year = int(p.stem)
        except ValueError:
            year = None
        if start_year is not None and year is not None and year < start_year:
            continue
        if end_year is not None and year is not None and year > end_year:
            continue
        status = "PASS"
        note = ""
        try:
            df = pl.read_parquet(p)
            missing = [c for c in REQUIRED if c not in df.columns]
            if missing:
                status = "FAIL"
                note = f"missing columns: {missing}"
                canonical = None
            else:
                canonical = canonicalize_validated_df(df)
            if status == "PASS" and canonical is not None and any(canonical[c].null_count() for c in REQUIRED):
                status = "FAIL"
                nulls = {c: int(canonical[c].null_count()) for c in REQUIRED if canonical[c].null_count()}
                note = f"null required values: {nulls}"
            elif status == "PASS" and canonical is not None and canonical["ts_event"].n_unique() != canonical.height:
                status = "FAIL"
                note = "duplicate ts_event"
            elif status == "PASS" and canonical is not None and canonical.filter(
                (pl.col("high") < pl.col("low"))
                | (pl.col("open") > pl.col("high"))
                | (pl.col("open") < pl.col("low"))
                | (pl.col("close") > pl.col("high"))
                | (pl.col("close") < pl.col("low"))
            ).height:
                status = "FAIL"
                note = "invalid OHLC ordering"
            elif write_validated:
                out = validated_root / p.parent.name / p.name
                out.parent.mkdir(parents=True, exist_ok=True)
                clean = canonical.drop_nulls(REQUIRED).sort("ts_event") if clean_policy == "drop-invalid" else canonical
                clean.write_parquet(out)
        except Exception as exc:
            status = "FAIL"
            note = str(exc)
        if status == "FAIL":
            failures.append(str(p))
        rows.append({"path": str(p), "market": p.parent.name, "year": p.stem, "status": status, "note": note})
    report = {
        "status": "FAIL" if failures else "PASS",
        "raw_root": str(raw_root),
        "validated_root": str(validated_root),
        "markets": sorted(market_set) if market_set else [],
        "start_year": start_year,
        "end_year": end_year,
        "files": rows,
        "failures": failures,
    }
    atomic_write_json("reports/validation/raw_validation_report.json", report)
    write_csv_rows("reports/validation/raw_validation_summary.csv", rows or [{"path": "", "market": "", "year": "", "status": "WARN", "note": "no raw files"}])
    if write_validated:
        build_data_manifest(validated_root, stage="validated")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audit-only", action="store_true")
    p.add_argument("--write-validated", action="store_true")
    p.add_argument("--clean-policy", choices=["drop-invalid", "none"], default="drop-invalid")
    p.add_argument("--raw-root", default="data/raw")
    p.add_argument("--validated-root", default="data/validated")
    p.add_argument("--markets", help="Comma-separated markets to process, e.g. ES,CL,ZN")
    p.add_argument("--start-year", type=int)
    p.add_argument("--end-year", type=int)
    args = p.parse_args()
    if not args.audit_only and not args.write_validated:
        args.audit_only = True
    report = validate_raw_to_validated(
        args.raw_root,
        args.validated_root,
        write_validated=args.write_validated,
        clean_policy=args.clean_policy,
        markets=_parse_csv(args.markets),
        start_year=args.start_year,
        end_year=args.end_year,
    )
    print(report["status"])


if __name__ == "__main__":
    main()
