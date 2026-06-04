import json

import polars as pl
import pytest

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
        verification_rows=[
            {"run_id": "old", "symbol": "ES", "split": 1, "pnl": 99, "sharpe_annualized": 9},
            {"run_id": "new", "symbol": "CL", "split": 1, "pnl": 1, "sharpe_annualized": 1},
        ],
        artifact_rows=[
            {"run_id": "old", "symbol": "ES", "split": 1, "status": "OK", "acceptance_status": "REJECT"},
            {"run_id": "new", "symbol": "CL", "split": 1, "status": "OK", "acceptance_status": "ACCEPT"},
        ],
    )
    assert comparison["active_splits"] == 1
    assert outliers == []
    reasons = json.loads((tmp_path / "reports/validation/acceptance_reasons.json").read_text(encoding="utf-8"))
    assert len(reasons) == 1
    assert reasons[0]["run_id"] == "new"
    assert reasons[0]["symbol"] == "CL"


def test_production_fixed_threshold_still_unchanged():
    config_module._LOADED = False
    cfg = config_module.load_config("tier_1_bare_minimum_alpha")
    assert cfg.execution.threshold_mode == "fixed"
    assert cfg.execution.prediction_entry_threshold == 0.25


def test_outlier_pnl_contribution_math_and_symbol_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "ES", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 10},
        {"run_id": "r1", "symbol": "ES", "split": 2, "test_active_bar_pct": 0.01, "test_turnover": 500},
        {"run_id": "r1", "symbol": "CL", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 20},
    ]), encoding="utf-8")
    es1 = tmp_path / "es1.parquet"
    es2 = tmp_path / "es2.parquet"
    cl1 = tmp_path / "cl1.parquet"
    pl.DataFrame({"gross_pnl": [120.0]}).write_parquet(es1)
    pl.DataFrame({"gross_pnl": [250.0]}).write_parquet(es2)
    pl.DataFrame({"gross_pnl": [-40.0]}).write_parquet(cl1)

    comparison, outliers = write_experiment_reports(
        run_id="r1",
        profile="p",
        expected_rows=3,
        verification_rows=[
            {"symbol": "ES", "split": 1, "pnl": 100.0, "sharpe_annualized": 1.0, "path": str(es1)},
            {"symbol": "ES", "split": 2, "pnl": 200.0, "sharpe_annualized": 2.0, "path": str(es2)},
            {"symbol": "CL", "split": 1, "pnl": -50.0, "sharpe_annualized": -1.0, "path": str(cl1)},
        ],
        artifact_rows=[
            {"symbol": "ES", "split": 1, "status": "OK", "acceptance_status": "ACCEPT"},
            {"symbol": "ES", "split": 2, "status": "OK", "acceptance_status": "REJECT"},
            {"symbol": "CL", "split": 1, "status": "OK", "acceptance_status": "REJECT"},
        ],
    )

    assert len(outliers) == 1
    assert comparison["outlier_count"] == 1
    assert comparison["accepted_outlier_count"] == 0
    assert comparison["rejected_outlier_count"] == 1
    assert comparison["net_pnl"] == 250.0
    assert comparison["outlier_pnl"] == 200.0
    assert comparison["non_outlier_pnl"] == 50.0
    assert comparison["outlier_pnl_pct_of_net"] == pytest.approx(0.8)
    assert comparison["outlier_turnover"] == 500.0
    assert comparison["non_outlier_turnover"] == 30.0
    assert comparison["outlier_turnover_pct_of_total"] == pytest.approx(500.0 / 530.0)
    assert comparison["cost_drag"] == 80.0
    assert comparison["cost_drag_pct_of_gross"] == pytest.approx(80.0 / 330.0)
    assert comparison["best_symbol_by_net_pnl"] == "ES"
    assert comparison["worst_symbol_by_net_pnl"] == "CL"

    symbol_rows = json.loads((tmp_path / "reports/validation/symbol_contribution.json").read_text(encoding="utf-8"))
    by_symbol = {r["symbol"]: r for r in symbol_rows}
    assert by_symbol["ES"]["net_pnl"] == 300.0
    assert by_symbol["ES"]["turnover"] == 510.0
    assert by_symbol["ES"]["outlier_count"] == 1
    assert by_symbol["ES"]["outlier_pnl"] == 200.0
    assert by_symbol["ES"]["non_outlier_pnl"] == 100.0
    assert by_symbol["CL"]["net_pnl"] == -50.0


def test_acceptance_reasons_written_for_all_90_splits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    symbols = ["CL", "ES", "ZN"]
    threshold_rows = [
        {"run_id": "r90", "symbol": symbol, "split": split, "test_active_bar_pct": 0.01, "test_turnover": split}
        for symbol in symbols
        for split in range(1, 31)
    ]
    p.write_text(json.dumps(threshold_rows), encoding="utf-8")
    rejection_path = tmp_path / "reject.json"
    rejection_path.write_text(json.dumps({
        "status": "REJECT",
        "gates": [
            {"name": "positive_net_pnl", "status": "FAIL"},
            {"name": "min_oos_sharpe", "status": "PASS"},
        ],
    }), encoding="utf-8")

    verification_rows = [
        {
            "run_id": "r90",
            "symbol": row["symbol"],
            "split": row["split"],
            "pnl": -1.0,
            "gross_pnl": 2.0,
            "sharpe_annualized": -0.1,
        }
        for row in threshold_rows
    ]
    artifact_rows = [
        {
            "run_id": "r90",
            "symbol": row["symbol"],
            "split": row["split"],
            "status": "OK",
            "acceptance_status": "REJECT",
            "acceptance_report": str(rejection_path),
        }
        for row in threshold_rows
    ]
    write_experiment_reports(
        run_id="r90",
        profile="p999",
        expected_rows=90,
        verification_rows=verification_rows,
        artifact_rows=artifact_rows,
    )
    reasons = json.loads((tmp_path / "reports/validation/acceptance_reasons.json").read_text(encoding="utf-8"))
    assert len(reasons) == 90
    assert {r["rejection_reason"] for r in reasons} == {"positive_net_pnl"}


def test_cost_drag_math_and_symbol_ablation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "CL", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 10},
        {"run_id": "r1", "symbol": "ES", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 20},
        {"run_id": "r1", "symbol": "ZN", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 30},
    ]), encoding="utf-8")
    write_experiment_reports(
        run_id="r1",
        profile="p999",
        expected_rows=3,
        verification_rows=[
            {"run_id": "r1", "symbol": "CL", "split": 1, "pnl": 70.0, "gross_pnl": 100.0, "sharpe_annualized": 1.0},
            {"run_id": "r1", "symbol": "ES", "split": 1, "pnl": 30.0, "gross_pnl": 50.0, "sharpe_annualized": 0.5},
            {"run_id": "r1", "symbol": "ZN", "split": 1, "pnl": -10.0, "gross_pnl": 10.0, "sharpe_annualized": -1.0},
        ],
        artifact_rows=[
            {"run_id": "r1", "symbol": "CL", "split": 1, "status": "OK", "acceptance_status": "ACCEPT"},
            {"run_id": "r1", "symbol": "ES", "split": 1, "status": "OK", "acceptance_status": "REJECT"},
            {"run_id": "r1", "symbol": "ZN", "split": 1, "status": "OK", "acceptance_status": "REJECT"},
        ],
    )
    cost_rows = json.loads((tmp_path / "reports/validation/cost_contribution.json").read_text(encoding="utf-8"))
    by_symbol = {r["symbol"]: r for r in cost_rows}
    assert by_symbol["CL"]["cost_drag"] == 30.0
    assert by_symbol["CL"]["cost_drag_pct_of_gross"] == pytest.approx(0.3)
    assert by_symbol["CL"]["pnl_per_turnover"] == pytest.approx(7.0)
    assert by_symbol["CL"]["accepted"] == 1
    assert by_symbol["ES"]["rejected"] == 1

    ablation = json.loads((tmp_path / "reports/validation/symbol_ablation.json").read_text(encoding="utf-8"))
    by_excluded = {r["excluded_symbol"]: r for r in ablation}
    assert by_excluded[""]["included_symbols"] == "CL,ES,ZN"
    assert by_excluded[""]["net_pnl"] == 90.0
    assert by_excluded[""]["gross_pnl"] == 160.0
    assert by_excluded[""]["cost_drag"] == 70.0
    assert by_excluded[""]["turnover"] == 60.0
    assert by_excluded["CL"]["included_symbols"] == "ES,ZN"
    assert by_excluded["CL"]["net_pnl"] == 20.0
    assert by_excluded["CL"]["ACCEPT"] == 0
    assert by_excluded["CL"]["REJECT"] == 2


def test_gate_near_miss_identifies_profitable_rejects_and_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "CL", "split": 1, "test_active_bar_pct": 0.01, "test_turnover": 10},
        {"run_id": "r1", "symbol": "ES", "split": 1, "test_active_bar_pct": 0.02, "test_turnover": 20},
        {"run_id": "old", "symbol": "ZN", "split": 1, "test_active_bar_pct": 0.03, "test_turnover": 30},
    ]), encoding="utf-8")
    min_trades_report = tmp_path / "min_trades.json"
    min_trades_report.write_text(json.dumps({
        "status": "REJECT",
        "gates": [{"name": "min_trades", "status": "FAIL"}],
    }), encoding="utf-8")
    multi_fail_report = tmp_path / "multi_fail.json"
    multi_fail_report.write_text(json.dumps({
        "status": "REJECT",
        "gates": [
            {"name": "min_oos_sharpe", "status": "FAIL"},
            {"name": "max_drawdown_pct", "status": "FAIL"},
        ],
    }), encoding="utf-8")

    write_experiment_reports(
        run_id="r1",
        profile="p999",
        expected_rows=2,
        verification_rows=[
            {"run_id": "r1", "symbol": "CL", "split": 1, "pnl": 10.0, "gross_pnl": 15.0, "sharpe_annualized": 0.1},
            {"run_id": "r1", "symbol": "ES", "split": 1, "pnl": 5.0, "gross_pnl": 8.0, "sharpe_annualized": -0.2},
            {"run_id": "old", "symbol": "ZN", "split": 1, "pnl": 99.0, "gross_pnl": 100.0, "sharpe_annualized": 9.0},
        ],
        artifact_rows=[
            {"run_id": "r1", "symbol": "CL", "split": 1, "status": "OK", "acceptance_status": "REJECT", "acceptance_report": str(min_trades_report)},
            {"run_id": "r1", "symbol": "ES", "split": 1, "status": "OK", "acceptance_status": "REJECT", "acceptance_report": str(multi_fail_report)},
            {"run_id": "old", "symbol": "ZN", "split": 1, "status": "OK", "acceptance_status": "REJECT", "acceptance_report": str(min_trades_report)},
        ],
    )

    near_miss = json.loads((tmp_path / "reports/validation/gate_near_miss.json").read_text(encoding="utf-8"))
    assert len(near_miss) == 2
    by_symbol = {r["symbol"]: r for r in near_miss}
    assert by_symbol["CL"]["positive_rejected"] == 1
    assert by_symbol["CL"]["failed_gate_count"] == 1
    assert by_symbol["CL"]["failed_gates"] == "min_trades"
    assert by_symbol["CL"]["failed_only_min_trades"] == 1
    assert by_symbol["CL"]["failed_min_trades_and_profitable"] == 1
    assert by_symbol["ES"]["failed_only_min_oos_sharpe"] == 0
    assert by_symbol["ES"]["failed_drawdown_and_profitable"] == 1
    assert {r["run_id"] for r in near_miss} == {"r1"}

    summary = json.loads((tmp_path / "reports/validation/gate_failure_summary.json").read_text(encoding="utf-8"))
    by_gate = {r["gate"]: r for r in summary}
    assert by_gate["min_trades"]["failed_count"] == 1
    assert by_gate["min_trades"]["failed_positive_net_count"] == 1
    assert by_gate["min_trades"]["failed_positive_net_pnl_sum"] == 10.0
    assert by_gate["min_trades"]["symbols_affected"] == "CL"
    assert by_gate["max_drawdown_pct"]["failed_count"] == 1
    assert by_gate["min_oos_sharpe"]["failed_count"] == 1
