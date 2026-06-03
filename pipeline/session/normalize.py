from __future__ import annotations

from pathlib import Path

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.data_gate.manifest import build_data_manifest


def normalize_session_df(df: pl.DataFrame, market: str = "") -> pl.DataFrame:
    if "ts_event" not in df.columns:
        raise ValueError("missing ts_event")
    out = df.sort("ts_event").unique("ts_event", keep="first")
    if out["ts_event"].dtype in (pl.Int64, pl.Int32, pl.UInt64, pl.UInt32):
        session_expr = (pl.col("ts_event") // 1440).cast(pl.Utf8)
    else:
        session_expr = pl.col("ts_event").dt.date().cast(pl.Utf8)
    return out.with_columns(
        session_expr.alias("session_id"),
        pl.lit(market).alias("market"),
    )


def session_normalize_root(in_root: str | Path = "data/validated", out_root: str | Path = "data/session_normalized", sessions_path: str | Path = "data/market_sessions.yaml") -> dict:
    in_root = Path(in_root)
    out_root = Path(out_root)
    rows = []
    failures = []
    for p in sorted(in_root.glob("*/*.parquet")):
        try:
            out = out_root / p.parent.name / p.name
            out.parent.mkdir(parents=True, exist_ok=True)
            normalize_session_df(pl.read_parquet(p), p.parent.name).write_parquet(out)
            rows.append({"input": str(p), "output": str(out), "status": "PASS"})
        except Exception as exc:
            failures.append(str(p))
            rows.append({"input": str(p), "output": "", "status": "FAIL", "note": str(exc)})
    report = {"status": "FAIL" if failures else "PASS", "sessions_path": str(sessions_path), "files": rows, "failures": failures}
    atomic_write_json("reports/session_normalization/session_normalization_report.json", report)
    write_csv_rows("reports/session_normalization/session_normalization_summary.csv", rows or [{"input": "", "output": "", "status": "WARN", "note": "no files"}])
    build_data_manifest(out_root, stage="session_normalized")
    return report

