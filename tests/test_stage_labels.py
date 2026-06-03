import polars as pl
import math

from pipeline.labels.generate import add_labels


def test_labels_respect_entry_lag_and_horizon():
    df = pl.DataFrame({"ts_event": list(range(8)), "open": [100.0, 101, 102, 104, 108, 109, 110, 111]})
    out = add_labels(df, horizon=2, entry_lag_bars=1, target_col="target_15m_ret", target_scale_factor=1.0)
    expected = (104.0 / 101.0)
    actual = math.exp(float(out["target_15m_ret"][0]))
    assert abs(actual - expected) < 1e-12
    assert out["label_entry_lag_bars"][0] == 1
