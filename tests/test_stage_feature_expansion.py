import polars as pl

from pipeline.common.config import PipelineConfig, RootConfig
from pipeline.features.expansion import expand_features


def test_feature_expansion_optional_and_excludes_leakage_columns():
    df = pl.DataFrame({"ret_lag_1": [1.0, 2.0], "roll_vol_5": [0.5, 0.25], "target_15m_ret": [1.0, 2.0], "future_bad": [3.0, 4.0]})
    disabled = expand_features(df, RootConfig(pipeline=PipelineConfig(enable_expansion=False)))
    assert disabled.columns == df.columns
    out = expand_features(df, RootConfig())
    assert "xp_ret_vol_ratio" in out.columns
    assert not any(c.startswith("xp_target") or "future_bad" in c for c in out.columns if c.startswith("xp_"))


def test_expanded_ohlcv_features_are_generated_and_present():
    df = pl.DataFrame(
        {
            "ts_event": pl.datetime_range(__import__("datetime").datetime(2025, 1, 1), __import__("datetime").datetime(2025, 1, 1, 0, 9), interval="1m", eager=True),
            "session_id": ["s1"] * 10,
            "open": [100.0 + i for i in range(10)],
            "high": [101.0 + i for i in range(10)],
            "low": [99.0 + i for i in range(10)],
            "close": [100.5 + i for i in range(10)],
            "volume": [1000.0 + i for i in range(10)],
            "target_15m_ret": [0.0] * 10,
        }
    )

    out = expand_features(df, RootConfig())

    expected = {
        "ret_1", "ret_3", "ret_5", "ret_lag_3", "roll_vol_15", "roll_range_15",
        "roll_volume_15", "volume_z_15", "bar_range", "body_to_range",
        "dist_ema_15", "slope_ema_15", "pos_in_15m_range",
        "minute_of_day_sin", "minute_of_day_cos", "day_of_week",
    }
    assert expected.issubset(set(out.columns))


def test_rolling_features_do_not_cross_session_boundaries():
    df = pl.DataFrame(
        {
            "ts_event": pl.datetime_range(__import__("datetime").datetime(2025, 1, 1), __import__("datetime").datetime(2025, 1, 1, 0, 5), interval="1m", eager=True),
            "session_id": ["s1", "s1", "s1", "s2", "s2", "s2"],
            "open": [100.0, 101.0, 102.0, 200.0, 201.0, 202.0],
            "high": [101.0, 102.0, 103.0, 201.0, 202.0, 203.0],
            "low": [99.0, 100.0, 101.0, 199.0, 200.0, 201.0],
            "close": [100.0, 101.0, 102.0, 200.0, 201.0, 202.0],
            "volume": [1000.0] * 6,
            "target_15m_ret": [0.0] * 6,
        }
    )

    out = expand_features(df, RootConfig())

    # First bar of s2 must not use previous session close near 102.
    assert out["ret_1"][3] == 0.0
