import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.common.config import DataSectionConfig, RootConfig
import pipeline.common.config as config_module
from pipeline.data_gate.manifest import build_data_manifest
from pipeline.stage_contract import assert_wfa_ready_root, stage_contracts, validate_stage_order_contract


REPO = Path(__file__).resolve().parents[1]


def _baseline_df(n=1500, *, include_target=True):
    start = datetime(2025, 1, 1, 9, 30)
    data = {
        "ts_event": [start + timedelta(hours=4 * i) for i in range(n)],
        "open": [5000.0 + i for i in range(n)],
        "high": [5001.0 + i for i in range(n)],
        "low": [4999.0 + i for i in range(n)],
        "close": [5000.5 + i for i in range(n)],
        "volume": [100 + i for i in range(n)],
        "x": [float(i % 11) for i in range(n)],
        "target_valid": [True] * n,
    }
    if include_target:
        data["target_15m_ret"] = [0.01 if i % 2 else -0.01 for i in range(n)]
    return pl.DataFrame(data)


def _write_baseline(root: Path, *, include_target=True):
    p = root / "ES" / "2025.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    _baseline_df(include_target=include_target).write_parquet(p)
    (root / "column_registry.json").write_text(
        '{"feature_columns":["x"],"target_columns":["target_15m_ret"]}',
        encoding="utf-8",
    )
    build_data_manifest(root, stage="baseline_feature_matrix")
    return p


def _env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["CONFIG_ENV"] = "tier_0_smoke_pipeline"
    env["QUANT_MODELING_MODE"] = "minimal_compatible"
    return env


def test_stage_order_contract_passes():
    assert validate_stage_order_contract("target_15m_ret")["status"] == "PASS"


def test_27_stages_registered_once_and_in_order():
    contracts = stage_contracts("target_15m_ret")
    assert [c.stage_index for c in contracts] == list(range(1, 28))
    assert len({c.stage_name for c in contracts}) == 27


def test_each_stage_has_input_output_contract():
    for contract in stage_contracts("target_15m_ret"):
        if contract.stage_index != 1:
            assert contract.expected_input_paths
        assert contract.expected_output_paths
        assert contract.validation_gate


def test_final_wfa_requires_frozen_feature_set_contract():
    final_wfa = next(c for c in stage_contracts("target_15m_ret") if c.stage_index == 24)
    assert any("frozen_features" in p for p in final_wfa.expected_input_paths)
    assert 23 in final_wfa.upstream_dependencies


def test_wfa_contract_rejects_non_matrix_stage(tmp_path):
    try:
        assert_wfa_ready_root(
            start_stage="raw",
            root=tmp_path / "data/raw",
            config=RootConfig(),
            checkpoint_mode=False,
        )
    except RuntimeError as exc:
        assert "is not WFA-ready" in str(exc)
        assert "baseline_feature_matrix" in str(exc)
    else:
        raise AssertionError("expected non-WFA-ready stage rejection")


def test_missing_target_in_baseline_matrix_is_actionable(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root, include_target=False)
    cfg = RootConfig(symbols=["ES"], start_year=2025, end_year=2025, data=DataSectionConfig(root=str(root)))

    try:
        assert_wfa_ready_root(
            start_stage="baseline_feature_matrix",
            root=root,
            config=cfg,
            checkpoint_mode=True,
            fail_prefix="CHECKPOINT TARGET INTEGRITY FAIL",
        )
    except RuntimeError as exc:
        text = str(exc)
        assert "target_15m_ret" in text
        assert str(root) in text
        assert "checkpoint_mode=True" in text
        assert "--from-stage baseline_feature_matrix" in text
    else:
        raise AssertionError("expected missing-target failure")


def test_default_run_fails_before_wfa_feasibility(tmp_path):
    result = subprocess.run(
        [sys.executable, str(REPO / "run.py")],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=30,
    )
    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert "[RUN RESOLUTION]" in out
    assert "start_stage=raw" in out
    assert "DEFAULT RUN FAIL" in out
    assert "WFA FEASIBILITY FAIL" not in out


def test_checkpoint_missing_target_fails_before_wfa_feasibility(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root, include_target=False)
    result = subprocess.run(
        [sys.executable, str(REPO / "run.py"), "--from-stage", "baseline_feature_matrix", "--data-root", str(root)],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=60,
    )
    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert "CHECKPOINT GATE FAIL" in out
    assert "missing configured target column: target_15m_ret" in out
    assert "--from-stage baseline_feature_matrix" in out
    assert "WFA FEASIBILITY FAIL" not in out


def test_baseline_checkpoint_command_validates_before_wfa(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root, include_target=True)
    result = subprocess.run(
        [sys.executable, str(REPO / "run.py"), "--from-stage", "baseline_feature_matrix", "--data-root", str(root)],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=90,
    )
    out = result.stdout + result.stderr
    assert "[CHECKPOINT START]" in out
    assert "checkpoint_gate=PASS" in out
    assert "WFA FEASIBILITY FAIL" not in out


def test_production_and_threshold_profiles_unchanged(monkeypatch):
    monkeypatch.delenv("CONFIG_ENV", raising=False)
    monkeypatch.delenv("QUANT_ENV", raising=False)
    config_module._LOADED = False
    prod = config_module.load_config("tier_1_bare_minimum_alpha")
    config_module._LOADED = False
    p995 = config_module.load_config("tier_1_threshold_p995_experiment")
    config_module._LOADED = False
    p999 = config_module.load_config("tier_1_threshold_p999_experiment")

    assert prod.execution.threshold_mode == "fixed"
    assert prod.execution.prediction_entry_threshold == 0.25
    assert prod.walkforward.walkforward_target == "target_15m_ret"
    assert p995.execution.threshold_mode == "prediction_abs_quantile"
    assert p995.execution.threshold_quantile == 0.995
    assert p999.execution.threshold_mode == "prediction_abs_quantile"
    assert p999.execution.threshold_quantile == 0.999
