from pipeline.common.config import PipelineConfig, RootConfig
from pipeline.gates.acceptance import run_acceptance_gate


def test_acceptance_gate_rejects_low_sharpe():
    cfg = RootConfig()
    report = run_acceptance_gate({"sharpe": 0.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0}, context={"config": cfg})
    assert report["status"] == "REJECT"


def test_acceptance_gate_rejects_very_negative_metrics():
    cfg = RootConfig()
    report = run_acceptance_gate(
        {"net_pnl": -100000.0, "sharpe": -5.0, "trades": 100, "max_drawdown_pct": -0.8, "profit_factor": 0.1, "turnover_per_bar": 0.0},
        stress_report={"scenarios": [{"scenario": "2x_costs", "net_pnl": -1.0}, {"scenario": "delayed_1_bar", "net_pnl": -1.0}]},
        context={"config": cfg},
    )
    assert report["status"] == "REJECT"


def test_acceptance_gate_rejects_negative_pnl_bad_sharpe():
    cfg = RootConfig()
    report = run_acceptance_gate(
        {"net_pnl": -1.0, "sharpe": -0.1, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0},
        stress_report={"scenarios": [{"scenario": "2x_costs", "net_pnl": 1.0}, {"scenario": "delayed_1_bar", "net_pnl": 1.0}]},
        context={"config": cfg},
    )
    assert report["status"] == "REJECT"


def test_acceptance_gate_rejects_missing_required_stress():
    cfg = RootConfig()
    report = run_acceptance_gate({"net_pnl": 1.0, "sharpe": 1.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0}, context={"config": cfg})
    assert report["status"] == "REJECT"
    assert any(g["name"] == "positive_after_2x_costs" and g["status"] == "FAIL" for g in report["gates"])


def test_acceptance_gate_warns_for_clean_minimal_mode_not_strategy_acceptance():
    cfg = RootConfig()
    report = run_acceptance_gate(
        {"net_pnl": 100.0, "sharpe": 1.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0},
        stress_report={"scenarios": [{"scenario": "2x_costs", "net_pnl": 50.0}, {"scenario": "delayed_1_bar", "net_pnl": 50.0}]},
        context={"config": cfg},
    )
    assert report["status"] == "WARN"
    assert report["acceptance_type"] == "RESEARCH_PIPELINE_ONLY"


def test_acceptance_gate_accepts_clean_full_research_report():
    cfg = RootConfig(pipeline=PipelineConfig(modeling_mode="full_research"))
    report = run_acceptance_gate(
        {"net_pnl": 100.0, "sharpe": 1.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0},
        stress_report={"scenarios": [{"scenario": "2x_costs", "net_pnl": 50.0}, {"scenario": "delayed_1_bar", "net_pnl": 50.0}]},
        context={"config": cfg},
    )
    assert report["status"] == "ACCEPT"
