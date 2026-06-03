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

