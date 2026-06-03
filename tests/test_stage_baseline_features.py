import polars as pl

from pipeline.features.baseline import build_baseline_features


def test_baseline_features_are_causal_and_exclude_future_columns():
    df = pl.DataFrame({"ts_event": list(range(8)), "close": [100.0 + i for i in range(8)], "high": [101.0 + i for i in range(8)], "low": [99.0 + i for i in range(8)], "volume": [10 + i for i in range(8)], "target_15m_ret": [0.0] * 8, "future_bad": [1.0] * 8})
    out = build_baseline_features(df)
    assert "ret_lag_1" in out.columns
    assert "roll_vol_5" in out.columns
    assert "future_bad" not in out.columns
    assert not any(c.startswith("future_") for c in out.columns)


def test_baseline_features_sanitize_nonfinite_price_artifacts():
    df = pl.DataFrame(
        {
            "ts_event": list(range(6)),
            "close": [0.0, 0.0, 100.0, 101.0, 0.0, 102.0],
            "high": [1.0, 1.0, 101.0, 102.0, 1.0, 103.0],
            "low": [0.0, 0.0, 99.0, 100.0, 0.0, 101.0],
            "volume": [10, 11, 12, 13, 14, 15],
        }
    )
    out = build_baseline_features(df)
    for col in ["ret_lag_1", "roll_vol_5", "roll_range_1"]:
        assert out.filter(~pl.col(col).is_finite()).height == 0
