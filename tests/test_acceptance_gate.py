from pipeline.common.config import RootConfig
from pipeline.gates.acceptance import run_acceptance_gate


def test_acceptance_gate_rejects_low_sharpe():
    cfg = RootConfig()
    report = run_acceptance_gate({"sharpe": 0.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0}, context={"config": cfg})
    assert report["status"] == "REJECT"


def test_acceptance_gate_accepts_clean_report():
    cfg = RootConfig()
    report = run_acceptance_gate({"sharpe": 1.0, "trades": 100, "max_drawdown_pct": 0.0, "profit_factor": 2.0, "turnover_per_bar": 0.0}, context={"config": cfg})
    assert report["status"] == "ACCEPT"
