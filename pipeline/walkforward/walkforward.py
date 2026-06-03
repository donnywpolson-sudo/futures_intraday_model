from __future__ import annotations

from typing import Any

import polars as pl


def apply_walkforward_contract(
    df: pl.DataFrame,
    train_start: Any,
    train_end: Any,
    test_start: Any,
    test_end: Any,
    *,
    ts_col: str = "ts_event",
    target_horizon_bars: int = 0,
    embargo_bars: int = 0,
    purge_target_overlap: bool = True,
    entry_lag_bars: int = 1,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    if ts_col not in df.columns:
        raise ValueError(f"missing timestamp column: {ts_col}")
    with_idx = df.sort(ts_col).with_row_index("_wfa_row")
    train = _filter_window(with_idx, ts_col, train_start, train_end)
    test = _filter_window(with_idx, ts_col, test_start, test_end)
    if train.height and test.height:
        if train["_wfa_row"].max() >= test["_wfa_row"].min():
            raise ValueError("walkforward contract violation: train/test overlap")
    if embargo_bars > 0 and train.height and test.height:
        boundary = int(test["_wfa_row"].min())
        train = train.filter(pl.col("_wfa_row") < boundary - int(embargo_bars))
    if purge_target_overlap and test.height:
        last_allowed = int(test["_wfa_row"].max()) - int(target_horizon_bars) - int(entry_lag_bars)
        test = test.filter(pl.col("_wfa_row") <= last_allowed)
    return train.drop("_wfa_row"), test.drop("_wfa_row")


def _filter_window(df: pl.DataFrame, ts_col: str, start: Any, end: Any) -> pl.DataFrame:
    out = df
    dtype = df[ts_col].dtype
    if start is not None:
        out = out.filter(pl.col(ts_col) >= pl.lit(start).cast(dtype))
    if end is not None:
        out = out.filter(pl.col(ts_col) < pl.lit(end).cast(dtype))
    return out
