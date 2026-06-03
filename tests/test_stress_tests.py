import polars as pl

from pipeline.common.config import RootConfig
from pipeline.stress.stress_tests import run_stress_tests


def test_stress_tests_generate_cost_and_delay_scenarios(tmp_path):
    df = pl.DataFrame({"gross_pnl": [10.0, -1.0, 2.0], "pnl": [9.0, -2.0, 1.0], "fees": [0.5, 0.5, 0.5], "slippage": [0.5, 0.5, 0.5]})
    report = run_stress_tests(df, RootConfig(), tmp_path / "stress_report")
    names = {s["scenario"] for s in report["scenarios"]}
    assert "2x_costs" in names
    assert "3x_costs" in names
    assert "delayed_1_bar" in names
