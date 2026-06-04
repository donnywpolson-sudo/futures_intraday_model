import polars as pl

from pipeline.common.config import ExecutionConfig, RootConfig
from pipeline.validation.signal_activation import build_signal_activation_row, write_signal_activation_debug


def test_non_null_predictions_below_threshold_reason():
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.5))
    df = pl.DataFrame(
        {
            "prediction": [0.1, -0.2, 0.3],
            "raw_signal": [0, 0, 0],
            "position_after": [0, 0, 0],
            "position_delta": [0, 0, 0],
        }
    )
    row = build_signal_activation_row(df, symbol="ES", split=1, config=cfg)
    assert row["reason_if_flat"] == "predictions too small for threshold"


def test_constant_predictions_reason():
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.5))
    df = pl.DataFrame(
        {
            "prediction": [0.1, 0.1, 0.1],
            "raw_signal": [0, 0, 0],
            "position_after": [0, 0, 0],
            "position_delta": [0, 0, 0],
        }
    )
    row = build_signal_activation_row(df, symbol="ES", split=1, config=cfg)
    assert row["reason_if_flat"] == "predictions constant"


def test_missing_signal_column_reason():
    df = pl.DataFrame({"prediction": [0.1, -0.2], "position_after": [0, 0]})
    row = build_signal_activation_row(df, symbol="ES", split=1, config=RootConfig())
    assert row["reason_if_flat"] == "signal column missing"


def test_risk_gate_zeroes_positions_reason():
    df = pl.DataFrame(
        {
            "prediction": [1.0, -1.0],
            "raw_signal": [1, -1],
            "position_after": [0, 0],
            "position_delta": [0, 0],
            "risk_gate_applied": [True, True],
        }
    )
    row = build_signal_activation_row(df, symbol="ES", split=1, config=RootConfig())
    assert row["reason_if_flat"] == "risk gate forced flat"


def test_active_cl_like_split_records_nonzero_diagnostics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pl.DataFrame(
        {
            "prediction": [0.2, -0.3, 0.0, 0.4],
            "raw_signal": [1, -1, 0, 1],
            "position_after": [1, -1, 0, 1],
            "position_delta": [1, -2, 1, 1],
            "signal_entry_threshold": [0.0, 0.0, 0.0, 0.0],
        }
    )
    row = write_signal_activation_debug(df, symbol="CL", split=7, config=RootConfig())
    assert row["long_bars"] == 2
    assert row["short_bars"] == 1
    assert row["active_bar_pct"] == 0.75
    assert row["position_turnover"] == 5.0
    assert row["reason_if_flat"] == ""
    assert (tmp_path / "reports" / "validation" / "signal_activation_debug.csv").exists()
