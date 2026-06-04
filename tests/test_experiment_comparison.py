import json

import pipeline.common.config as config_module

from pipeline.validation.experiment_comparison import write_experiment_reports


def test_clean_run_writes_experiment_comparison(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    path = tmp_path / "reports/validation/threshold_used.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([
        {"run_id": "r1", "symbol": "ES", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 10},
    ]), encoding="utf-8")
    comparison, outliers = write_experiment_reports(
        run_id="r1",
        profile="p",
        expected_rows=1,
        verification_rows=[{"symbol": "ES", "split": 1, "pnl": 5.0, "sharpe_annualized": 1.2}],
        artifact_rows=[{"symbol": "ES", "split": 1, "status": "OK", "acceptance_status": "REJECT"}],
    )
    assert comparison["expected_rows"] == 1
    assert comparison["successful"] == 1
    assert comparison["REJECT"] == 1
    assert outliers == []
    assert (tmp_path / "reports/validation/experiment_comparison.csv").exists()


def test_outlier_active_pct_is_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "ZN", "split": 22, "test_active_bar_pct": 0.0818, "test_turnover": 100},
    ]), encoding="utf-8")
    _, outliers = write_experiment_reports(
        run_id="r1", profile="p", expected_rows=1,
        verification_rows=[{"symbol": "ZN", "split": 22, "pnl": -1, "sharpe_annualized": -2}],
        artifact_rows=[{"symbol": "ZN", "split": 22, "status": "OK", "acceptance_status": "REJECT"}],
    )
    assert len(outliers) == 1
    assert outliers[0]["symbol"] == "ZN"


def test_outlier_turnover_is_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "ES", "split": 4, "test_active_bar_pct": 0.01, "test_turnover": 502},
    ]), encoding="utf-8")
    _, outliers = write_experiment_reports(
        run_id="r1", profile="p", expected_rows=1,
        verification_rows=[{"symbol": "ES", "split": 4, "pnl": -1, "sharpe_annualized": -2}],
        artifact_rows=[{"symbol": "ES", "split": 4, "status": "OK", "acceptance_status": "REJECT"}],
    )
    assert len(outliers) == 1
    assert outliers[0]["test_turnover"] == 502.0


def test_reports_are_scoped_by_run_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "old", "symbol": "ES", "split": 1, "test_active_bar_pct": 0.9, "test_turnover": 999},
        {"run_id": "new", "symbol": "CL", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 10},
    ]), encoding="utf-8")
    comparison, outliers = write_experiment_reports(
        run_id="new", profile="p", expected_rows=1,
        verification_rows=[{"symbol": "CL", "split": 1, "pnl": 1, "sharpe_annualized": 1}],
        artifact_rows=[{"symbol": "CL", "split": 1, "status": "OK", "acceptance_status": "ACCEPT"}],
    )
    assert comparison["active_splits"] == 1
    assert outliers == []


def test_production_fixed_threshold_still_unchanged():
    config_module._LOADED = False
    cfg = config_module.load_config("tier_1_bare_minimum_alpha")
    assert cfg.execution.threshold_mode == "fixed"
    assert cfg.execution.prediction_entry_threshold == 0.25
