import polars as pl

from pipeline.walkforward.walkforward import apply_walkforward_contract


def test_walkforward_train_test_no_overlap():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    train, test = apply_walkforward_contract(df, 0, 5, 5, 10, target_horizon_bars=0, entry_lag_bars=0)
    assert train["ts_event"].max() < test["ts_event"].min()


def test_target_horizon_purge_near_test_end():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    _, test = apply_walkforward_contract(df, 0, 5, 5, 10, target_horizon_bars=2, entry_lag_bars=1)
    assert test["ts_event"].max() == 6


def test_embargo_removes_boundary_train_rows():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    train, _ = apply_walkforward_contract(df, 0, 5, 5, 10, embargo_bars=2, target_horizon_bars=0, entry_lag_bars=0)
    assert train["ts_event"].to_list() == [0, 1, 2]
