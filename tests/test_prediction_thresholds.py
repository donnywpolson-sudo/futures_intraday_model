import polars as pl

from pipeline.common.config import ExecutionConfig, RootConfig
from pipeline.validation.prediction_thresholds import (
    build_prediction_threshold_diagnostics,
    print_threshold_diagnostic_summary,
    write_prediction_threshold_diagnostics,
)


def test_current_threshold_larger_than_predictions_reports_near_zero_active_pct():
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.25))
    df = pl.DataFrame({"prediction": [-0.001, 0.0, 0.001]})
    row, _ = build_prediction_threshold_diagnostics(df, symbol="ES", split=1, config=cfg)
    assert row["active_pct_at_current_threshold"] == 0.0
    assert row["bars_above_current_long"] == 0
    assert row["bars_below_current_short"] == 0


def test_p99_candidate_threshold_activates_about_one_pct():
    preds = [i / 1_000_000 for i in range(1000)]
    df = pl.DataFrame({"prediction": preds})
    _, grid = build_prediction_threshold_diagnostics(df, symbol="ES", split=1, config=RootConfig())
    p99 = next(r for r in grid if r["threshold_type"] == "p99")
    assert 0.005 <= p99["active_bar_pct"] <= 0.015


def test_p995_candidate_threshold_activates_about_half_pct():
    preds = [i / 1_000_000 for i in range(1000)]
    df = pl.DataFrame({"prediction": preds})
    _, grid = build_prediction_threshold_diagnostics(df, symbol="ES", split=1, config=RootConfig())
    p995 = next(r for r in grid if r["threshold_type"] == "p995")
    assert 0.002 <= p995["active_bar_pct"] <= 0.008


def test_candidate_grid_includes_fixed_and_quantile_thresholds():
    df = pl.DataFrame({"prediction": [i / 1000 for i in range(-100, 101)]})
    _, grid = build_prediction_threshold_diagnostics(df, symbol="CL", split=7, config=RootConfig())
    types = {r["threshold_type"] for r in grid}
    assert {"p90", "p95", "p99", "p995", "p999", "fixed_0.001", "fixed_0.25"}.issubset(types)


def test_threshold_reports_and_summary_print(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    df = pl.DataFrame({"prediction": [i / 1000 for i in range(-100, 101)]})
    write_prediction_threshold_diagnostics(df, symbol="CL", split=1, config=RootConfig())
    print_threshold_diagnostic_summary(expected_splits=1, expected_run_id="manual")
    out = capsys.readouterr().out
    assert "[THRESHOLD DIAG] current threshold active splits=" in out
    assert "candidate threshold p99" in out
    assert (tmp_path / "reports" / "validation" / "prediction_threshold_diagnostics.csv").exists()
    assert (tmp_path / "reports" / "validation" / "threshold_candidate_grid.csv").exists()
