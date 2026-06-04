from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import write_csv_rows


REPORT_CSV = Path("reports/validation/target_integrity.csv")
REPORT_JSON = Path("reports/validation/target_integrity.json")


def target_col_from_config(config: Any | None, default: str = "target_15m_ret") -> str:
    return str(getattr(getattr(config, "walkforward", object()), "walkforward_target", default))


def choose_target_group_cols(df: pl.DataFrame, min_rows: int) -> list[str]:
    candidates = [
        ["symbol", "session_id"],
        ["market", "session_id"],
        ["session_id"],
        ["symbol", "session_date"],
        ["market", "session_date"],
        ["session_date"],
    ]
    for cols in candidates:
        if all(c in df.columns for c in cols):
            sizes = df.group_by(cols).len()["len"].to_list()
            if sizes and max(sizes) >= min_rows:
                return cols
    if "symbol" in df.columns:
        return ["symbol"]
    if "market" in df.columns:
        return ["market"]
    return []


def add_forward_return_target(
    df: pl.DataFrame,
    *,
    horizon: int,
    entry_lag_bars: int,
    target_col: str = "target_15m_ret",
    target_scale_factor: float = 1.0,
    price_col: str = "open",
) -> tuple[pl.DataFrame, str, list[str]]:
    if price_col not in df.columns:
        price_col = "close"
    if price_col not in df.columns:
        raise ValueError("missing open/close for label generation")
    entry = int(entry_lag_bars)
    exit_lag = entry + int(horizon)
    group_cols = choose_target_group_cols(df, exit_lag + 1)
    entry_expr = pl.col(price_col).shift(-entry)
    exit_expr = pl.col(price_col).shift(-exit_lag)
    if group_cols:
        entry_expr = entry_expr.over(group_cols)
        exit_expr = exit_expr.over(group_cols)
    target_expr = ((exit_expr / entry_expr).log() * float(target_scale_factor)).alias(target_col)
    valid_expr = (
        entry_expr.is_not_null()
        & exit_expr.is_not_null()
        & entry_expr.cast(pl.Float64).is_finite()
        & exit_expr.cast(pl.Float64).is_finite()
    ).alias("target_valid")
    out = df.with_columns(
        target_expr,
        valid_expr,
        pl.lit(entry_lag_bars).alias("label_entry_lag_bars"),
        pl.lit(horizon).alias("label_horizon_bars"),
        pl.lit(float(target_scale_factor)).alias("label_target_scale_factor"),
    )
    return out, price_col, group_cols


def inspect_target_integrity(
    df: pl.DataFrame,
    *,
    symbol: str,
    file: str,
    target_col: str,
    close_col_used: str = "",
    group_col_used: str | list[str] = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": symbol,
        "file": file,
        "rows": df.height,
        "min_ts": str(df["ts_event"].min()) if "ts_event" in df.columns and df.height else "",
        "max_ts": str(df["ts_event"].max()) if "ts_event" in df.columns and df.height else "",
        "target_col": target_col,
        "target_nonnull": 0,
        "target_null_pct": 1.0,
        "target_valid_true": 0,
        "target_valid_true_and_target_nonnull": 0,
        "close_col_used": close_col_used or ("open" if "open" in df.columns else ("close" if "close" in df.columns else "")),
        "close_nonnull": int(df["close"].drop_nulls().len()) if "close" in df.columns else 0,
        "group_col_used": "|".join(group_col_used) if isinstance(group_col_used, list) else str(group_col_used or ""),
        "groups": 0,
        "rows_per_group_min": 0,
        "rows_per_group_median": 0,
        "rows_per_group_max": 0,
        "reason": "PASS",
    }
    if target_col not in df.columns:
        row["reason"] = f"config target_col missing from matrix: {target_col}"
        return row
    target_nonnull = int(df[target_col].drop_nulls().len())
    row["target_nonnull"] = target_nonnull
    row["target_null_pct"] = float(1.0 - (target_nonnull / max(df.height, 1)))
    if "target_valid" in df.columns:
        valid = df.filter(pl.col("target_valid").fill_null(False).cast(pl.Boolean))
        row["target_valid_true"] = valid.height
        row["target_valid_true_and_target_nonnull"] = int(valid[target_col].drop_nulls().len()) if target_col in valid.columns else 0
    else:
        row["target_valid_true"] = target_nonnull
        row["target_valid_true_and_target_nonnull"] = target_nonnull

    group_cols = [c for c in str(row["group_col_used"]).split("|") if c]
    if group_cols and all(c in df.columns for c in group_cols):
        sizes = df.group_by(group_cols).len()["len"].to_list()
        if sizes:
            sizes_sorted = sorted(int(x) for x in sizes)
            row["groups"] = len(sizes_sorted)
            row["rows_per_group_min"] = sizes_sorted[0]
            row["rows_per_group_median"] = sizes_sorted[len(sizes_sorted) // 2]
            row["rows_per_group_max"] = sizes_sorted[-1]

    if row["target_valid_true"] > 0 and row["target_valid_true_and_target_nonnull"] == 0:
        row["reason"] = "target_valid true but target null for all valid rows"
    elif target_nonnull == 0:
        row["reason"] = "target column all null"
    return row


def validate_target_integrity_row(row: dict[str, Any]) -> None:
    if row.get("reason") != "PASS":
        raise RuntimeError(f"TARGET INTEGRITY FAIL: {row.get('symbol')} {row.get('file')} reason={row.get('reason')}")


def write_target_integrity_report(rows: list[dict[str, Any]]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_csv_rows(REPORT_CSV, rows or [{"status": "WARN", "reason": "no files"}])
    REPORT_JSON.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")


def validate_target_integrity_root(root: str | Path, config: Any | None = None, *, fail_prefix: str = "TARGET INTEGRITY FAIL") -> list[dict[str, Any]]:
    root = Path(root)
    target_col = target_col_from_config(config)
    rows = []
    for p in sorted(root.glob("*/*.parquet")):
        df = pl.read_parquet(p)
        row = inspect_target_integrity(df, symbol=p.parent.name, file=str(p), target_col=target_col)
        rows.append(row)
    write_target_integrity_report(rows)
    bad = [r for r in rows if r.get("reason") != "PASS"]
    if bad:
        first = bad[0]
        raise RuntimeError(f"{fail_prefix}: regenerate baseline feature matrix from the target/features stage; reason={first.get('reason')} file={first.get('file')}")
    return rows
