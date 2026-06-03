import polars as pl

from pipeline.audit.execution_trace import validate_execution_trace
from pipeline.common.config import RootConfig


def test_execution_trace_rejects_same_bar_fill():
    trace = pl.DataFrame({"prediction_time": [1], "execution_time": [1], "fees": [0.0], "slippage": [0.0], "pnl": [1.0]})
    report = validate_execution_trace(trace, RootConfig())
    assert report["status"] == "FAIL"
