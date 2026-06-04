import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.common.config import ExecutionConfig, RootConfig
from pipeline.validation.final_threshold_diagnostics import write_final_threshold_diagnostics


def _df() -> pl.DataFrame:
    ts = [datetime(2025, 1, 1) + timedelta(minutes=i) for i in range(6)]
    return pl.DataFrame(
        {
            "run_id": ["run_test"] * 12,
            "profile": ["tier_1_bare_minimum_alpha"] * 12,
            "symbol": ["ES"] * 6 + ["CL"] * 6,
            "split": ["1"] * 6 + ["1"] * 6,
            "timestamp": ts + ts,
            "ts_event": ts + ts,
            "prediction": [0.001, -0.001, 0.0005, -0.0005, 0.0, 0.0001] + [0.3, 0.0, -0.3, 0.0, 0.0, 0.0],
            "raw_signal": [0] * 6 + [1, 0, -1, 0, 0, 0],
            "position": [0] * 6 + [1, 0, -1, 0, 0, 0],
            "position_after": [0] * 6 + [1, 0, -1, 0, 0, 0],
            "position_delta": [0] * 6 + [1, 1, 1, 1, 0, 0],
            "target_15m_ret": [0.0] * 12,
        }
    )


def test_final_flat_split_classified_predictions_too_small(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.25))

    write_final_threshold_diagnostics(df=_df(), config=cfg, run_id="run_test", profile="tier_1_bare_minimum_alpha")
    rows = json.loads(Path("reports/validation/final_signal_activation_debug.json").read_text())
    es = next(r for r in rows if r["symbol"] == "ES")

    assert es["reason_if_flat"] == "predictions too small for threshold"


def test_final_threshold_grid_candidates_and_run_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.25))

    write_final_threshold_diagnostics(df=_df(), config=cfg, run_id="run_test", profile="tier_1_bare_minimum_alpha")
    rows = json.loads(Path("reports/validation/final_threshold_candidate_grid.json").read_text())
    types = {r["threshold_type"] for r in rows}

    assert {"p99", "p995", "p999", "fixed_0.001", "fixed_0.0025", "fixed_0.005", "fixed_0.01", "fixed_0.025", "fixed_0.05", "fixed_0.1", "fixed_0.25"}.issubset(types)
    assert {r["run_id"] for r in rows} == {"run_test"}
    assert all(isinstance(r["split"], str) for r in rows)


def test_stage27_and_production_threshold_unchanged():
    cfg = RootConfig(execution=ExecutionConfig(prediction_entry_threshold=0.25))

    assert cfg.execution.prediction_entry_threshold == 0.25
    assert cfg.acceptance_gate.min_oos_sharpe == 0.25
    assert cfg.acceptance_gate.min_trades == 30
    assert cfg.acceptance_gate.max_drawdown_pct == -0.20
