import polars as pl

from pipeline.cli import _write_oos_predictions
from pipeline.common.config import ExecutionConfig, RootConfig
from pipeline.audit.execution_trace import validate_execution_trace
from pipeline.gates.acceptance import run_acceptance_gate
from pipeline.common.config import PipelineConfig


def test_oos_predictions_artifact_has_required_columns(tmp_path):
    df = pl.DataFrame(
        {
            "ts_event": [1],
            "prediction_time": [1],
            "execution_time": [2],
            "prediction": [0.1],
            "prediction_prob": [0.55],
            "target_15m_ret": [0.01],
            "feature_set_id": ["abc"],
        }
    )
    path = tmp_path / "oos_predictions.parquet"
    _write_oos_predictions(
        df,
        path,
        target_col="target_15m_ret",
        symbol="ES",
        split_id="1",
        train_start="0",
        train_end="1",
        test_start="1",
        test_end="2",
        modeling_mode="full_research",
    )
    out = pl.read_parquet(path)
    required = {"ts_event", "prediction_time", "execution_time", "prediction", "prediction_prob", "target_col", "target_value", "symbol", "split_id", "train_start", "train_end", "test_start", "test_end", "modeling_mode", "feature_set_id"}
    assert required.issubset(set(out.columns))


def test_execution_trace_entry_lag_costs_and_max_contracts():
    cfg = RootConfig(execution=ExecutionConfig(reject_same_bar_fill=True, entry_lag_bars=1, max_contracts=1))
    same_bar = pl.DataFrame({"prediction_time": [1], "execution_time": [1], "fees": [0.0], "slippage": [0.0], "pnl": [1.0], "gross_pnl": [1.0], "position_after": [1]})
    assert validate_execution_trace(same_bar, cfg)["status"] == "FAIL"
    ok = pl.DataFrame({"prediction_time": [1], "execution_time": [2], "fees": [1.0], "slippage": [0.5], "pnl": [8.5], "gross_pnl": [10.0], "position_after": [1]})
    assert validate_execution_trace(ok, cfg)["status"] == "PASS"
    too_big = ok.with_columns(pl.lit(2).alias("position_after"))
    assert validate_execution_trace(too_big, cfg)["status"] == "FAIL"


def test_acceptance_separates_pipeline_pass_from_strategy_acceptance():
    metrics = {"net_pnl": 100.0, "sharpe": 1.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0}
    stress = {"scenarios": [{"scenario": "2x_costs", "net_pnl": 50.0}, {"scenario": "delayed_1_bar", "net_pnl": 50.0}]}
    minimal = run_acceptance_gate(metrics, stress_report=stress, context={"config": RootConfig()})
    assert minimal["pipeline_acceptance_status"] == "PASS"
    assert minimal["strategy_acceptance_status"] == "NOT_EVALUATED"
    bad = run_acceptance_gate(
        {"net_pnl": -1.0, "sharpe": -1.0, "trades": 1, "max_drawdown_pct": -1.0, "profit_factor": 0.1, "turnover_per_bar": 99.0},
        stress_report={"scenarios": [{"scenario": "2x_costs", "net_pnl": -1.0}, {"scenario": "delayed_1_bar", "net_pnl": -1.0}]},
        context={"config": RootConfig(pipeline=PipelineConfig(modeling_mode="full_research"))},
    )
    assert bad["pipeline_acceptance_status"] == "FAIL"
    assert bad["strategy_acceptance_status"] == "REJECT"
    full = run_acceptance_gate(metrics, stress_report=stress, context={"config": RootConfig(pipeline=PipelineConfig(modeling_mode="full_research"))})
    assert full["strategy_acceptance_status"] == "ACCEPT"
