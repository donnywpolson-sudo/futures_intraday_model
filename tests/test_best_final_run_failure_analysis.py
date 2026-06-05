import json
from pathlib import Path

from pipeline.validation.best_final_run_failure_analysis import (
    BEST_FINAL_ANALYSIS_JSON,
    FINAL_GATE_PASS_RATES_JSON,
    FINAL_OUTLIER_IMPACT_JSON,
    write_best_final_run_failure_analysis,
)


def _write_json(path: str, payload):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _fixtures():
    _write_json(
        "reports/validation/frozen_set_comparison.json",
        [
            {"run_id": "run_low", "profile": "tier_1_final_threshold_p999_experiment", "artifact_available": True, "selected_feature_count": 4, "net_pnl": 10, "gross_pnl": 20, "cost_drag": 10, "cost_drag_pct_of_gross": 0.5, "ACCEPT": 1, "REJECT": 1, "outlier_count": 0},
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "artifact_available": True, "selected_feature_count": 30, "net_pnl": 100, "gross_pnl": 130, "cost_drag": 30, "cost_drag_pct_of_gross": 0.23, "ACCEPT": 1, "REJECT": 2, "outlier_count": 1},
            {"run_id": "run_missing", "profile": "tier_1_final_threshold_p999_experiment", "artifact_available": False, "selected_feature_count": "", "net_pnl": 999},
        ],
    )
    _write_json(
        "reports/validation/final_gate_breakdown.json",
        [
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "ES", "split": "1", "acceptance_status": "REJECT", "failed_gates": "min_trades,max_drawdown_pct", "net_pnl": 50, "gross_pnl": 60, "turnover": 4},
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "ES", "split": "2", "acceptance_status": "REJECT", "failed_gates": "min_trades", "net_pnl": -20, "gross_pnl": -10, "turnover": 2},
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "CL", "split": "1", "acceptance_status": "ACCEPT", "failed_gates": "", "net_pnl": 70, "gross_pnl": 80, "turnover": 3},
        ],
    )
    _write_json(
        "reports/validation/final_symbol_contribution.json",
        [
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "ES", "net_pnl": 30, "accepted": 0},
            {"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "CL", "net_pnl": 70, "accepted": 1},
        ],
    )
    _write_json(
        "reports/validation/final_threshold_outliers.json",
        [{"run_id": "run_best", "profile": "tier_1_final_threshold_p999_experiment", "symbol": "ES", "split": "1"}],
    )


def test_best_run_analysis_chooses_highest_available_net_pnl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fixtures()

    result = write_best_final_run_failure_analysis()
    row = json.loads(BEST_FINAL_ANALYSIS_JSON.read_text(encoding="utf-8"))[0]

    assert result["run_id"] == "run_best"
    assert row["run_id"] == "run_best"
    assert row["selected_feature_count"] == 30


def test_gate_pass_rates_count_failed_gates_correctly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fixtures()

    write_best_final_run_failure_analysis()
    rows = {r["gate"]: r for r in json.loads(FINAL_GATE_PASS_RATES_JSON.read_text(encoding="utf-8"))}

    assert rows["min_trades"]["fail_count"] == 2
    assert rows["min_trades"]["pass_count"] == 1
    assert rows["max_drawdown_pct"]["failed_positive_net_count"] == 1
    assert rows["max_drawdown_pct"]["failed_positive_net_pnl_sum"] == 50


def test_outlier_impact_math_and_run_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fixtures()

    write_best_final_run_failure_analysis()
    row = json.loads(FINAL_OUTLIER_IMPACT_JSON.read_text(encoding="utf-8"))[0]

    assert row["run_id"] == "run_best"
    assert row["outlier_count"] == 1
    assert row["outlier_net_pnl"] == 50
    assert row["non_outlier_net_pnl"] == 50
    assert row["outlier_turnover"] == 4
    assert row["non_outlier_turnover"] == 5


def test_production_config_and_gate_thresholds_unchanged(monkeypatch):
    import pipeline.common.config as config_module

    config_module._LOADED = False
    prod = config_module.load_config("tier_1_bare_minimum_alpha")

    assert prod.execution.threshold_mode == "fixed"
    assert prod.execution.prediction_entry_threshold == 0.25
    assert prod.acceptance_gate.min_trades == 30
