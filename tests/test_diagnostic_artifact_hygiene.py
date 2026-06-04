import json

import numpy as np
import polars as pl
import pytest

from pipeline.common.config import ExecutionConfig, RootConfig
from pipeline.validation.prediction_thresholds import (
    CANDIDATE_THRESHOLD_COUNT,
    print_threshold_diagnostic_summary,
    validate_current_run_diagnostics,
    write_prediction_threshold_diagnostics,
)
from pipeline.validation.signal_activation import write_signal_activation_debug
from pipeline.validation.threshold_used import resolve_threshold_from_train, threshold_used_row_count, write_threshold_used


def _df():
    return pl.DataFrame(
        {
            "prediction": [-0.2, 0.0, 0.2],
            "raw_signal": [-1, 0, 1],
            "position_after": [-1.0, 0.0, 1.0],
            "position_delta": [1.0, 1.0, 1.0],
            "signal_entry_threshold": [0.1, 0.1, 0.1],
        }
    )


def _write_all(symbol="ES", split=1):
    cfg = RootConfig(execution=ExecutionConfig(threshold_mode="prediction_abs_quantile", threshold_quantile=0.995))
    train = np.array([-0.1, 0.0, 0.1])
    threshold, _, _, _, train_q = resolve_threshold_from_train(train, cfg)
    df = _df()
    write_threshold_used(symbol=symbol, split=split, config=cfg, train_predictions=train, test_result=df, threshold=threshold, train_abs_prediction_quantile=train_q)
    write_signal_activation_debug(df, symbol=symbol, split=split, config=cfg)
    write_prediction_threshold_diagnostics(df, symbol=symbol, split=split, config=cfg)


def _write_non_threshold_reports(symbol="ES", split=1):
    cfg = RootConfig(execution=ExecutionConfig(threshold_mode="fixed", prediction_entry_threshold=0.25))
    df = _df()
    write_signal_activation_debug(df, symbol=symbol, split=split, config=cfg)
    write_prediction_threshold_diagnostics(df, symbol=symbol, split=split, config=cfg)


def test_repeated_runs_do_not_duplicate_threshold_used_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    _write_all("ES", 1)
    _write_all("ES", 1)
    rows = json.loads((tmp_path / "reports/validation/threshold_used.json").read_text())
    assert len(rows) == 1
    assert rows[0]["run_id"] == "r1"


def test_repeated_runs_do_not_duplicate_signal_activation_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    _write_all("CL", 2)
    _write_all("CL", 2)
    rows = json.loads((tmp_path / "reports/validation/signal_activation_debug.json").read_text())
    assert len(rows) == 1


def test_repeated_runs_do_not_duplicate_threshold_candidate_grid_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    _write_all("ZN", 3)
    _write_all("ZN", 3)
    rows = json.loads((tmp_path / "reports/validation/threshold_candidate_grid.json").read_text())
    assert len(rows) == CANDIDATE_THRESHOLD_COUNT


def test_active_splits_summary_cannot_exceed_expected_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    p = tmp_path / "reports/validation/prediction_threshold_diagnostics.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([
        {"run_id": "r1", "symbol": "ES", "split": 1, "active_pct_at_current_threshold": 0.1},
        {"run_id": "r1", "symbol": "CL", "split": 1, "active_pct_at_current_threshold": 0.1},
    ]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="THRESHOLD DIAG INTEGRITY FAIL"):
        print_threshold_diagnostic_summary(expected_splits=1)


def test_duplicate_symbol_split_in_threshold_used_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "r1")
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    duplicate = {"run_id": "r1", "symbol": "ES", "split": 1}
    p.write_text(json.dumps([duplicate, duplicate]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="THRESHOLD DIAG INTEGRITY FAIL"):
        validate_current_run_diagnostics(expected_rows=1)


def test_parent_run_id_overrides_child_run_id_for_threshold_used(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PARENT_RUN_ID", "parent123")
    monkeypatch.setenv("QUANT_RUN_ID", "child456")
    _write_all("ES", 4)

    rows = json.loads((tmp_path / "reports/validation/threshold_used.json").read_text())
    assert rows[0]["run_id"] == "parent123"
    assert threshold_used_row_count("parent123", "ES", 4) == 1
    assert threshold_used_row_count("child456", "ES", 4) == 0


def test_validator_details_when_rows_exist_under_different_run_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PARENT_RUN_ID", "expected_run")
    p = tmp_path / "reports/validation/threshold_used.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([{"run_id": "other_run", "profile": "p995", "symbol": "ES", "split": 1}]), encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        validate_current_run_diagnostics(expected_rows=1, require_threshold_used=True)

    msg = str(exc.value)
    assert "expected_run_id=expected_run" in msg
    assert "total_rows=1" in msg
    assert "unique_run_ids=['other_run']" in msg
    assert "unique_profiles=['p995']" in msg
    assert "first_5_rows=" in msg


def test_p995_requires_expected_threshold_used_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "p995run")
    _write_all("ES", 1)

    with pytest.raises(RuntimeError, match="threshold_used rows=1 expected=2"):
        validate_current_run_diagnostics(expected_rows=2, require_threshold_used=True)


def test_fixed_threshold_does_not_require_threshold_used(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUANT_RUN_ID", "fixedrun")
    _write_non_threshold_reports("ES", 1)

    result = validate_current_run_diagnostics(expected_rows=1, require_threshold_used=False)
    assert result["status"] == "PASS"
