import polars as pl

from pipeline.features.baseline import build_baseline_features


def test_baseline_features_are_causal_and_exclude_future_columns():
    df = pl.DataFrame({"ts_event": list(range(8)), "close": [100.0 + i for i in range(8)], "high": [101.0 + i for i in range(8)], "low": [99.0 + i for i in range(8)], "volume": [10 + i for i in range(8)], "target_15m_ret": [0.0] * 8, "future_bad": [1.0] * 8})
    out = build_baseline_features(df)
    assert "ret_lag_1" in out.columns
    assert "roll_vol_5" in out.columns
    assert "future_bad" not in out.columns
    assert not any(c.startswith("future_") for c in out.columns)

