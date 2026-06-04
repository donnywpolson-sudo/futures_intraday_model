import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.data_gate.manifest import build_data_manifest


REPO = Path(__file__).resolve().parents[1]


def _write_baseline(root: Path, *, include_target: bool = True) -> None:
    n = 40
    start = datetime(2025, 1, 1, 9, 30)
    data = {
        "ts_event": [start + timedelta(minutes=i) for i in range(n)],
        "open": [5000.0 + i for i in range(n)],
        "high": [5001.0 + i for i in range(n)],
        "low": [4999.0 + i for i in range(n)],
        "close": [5000.5 + i for i in range(n)],
        "volume": [100 + i for i in range(n)],
        "x": [float(i % 5) for i in range(n)],
        "target_valid": [True] * n,
    }
    if include_target:
        data["target_15m_ret"] = [0.01 if i % 2 else -0.01 for i in range(n)]
    p = root / "ES" / "2025.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(data).write_parquet(p)
    (root / "column_registry.json").write_text(
        '{"feature_columns":["x"],"target_columns":["target_15m_ret"]}',
        encoding="utf-8",
    )
    build_data_manifest(root, stage="baseline_feature_matrix")


def _env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["CONFIG_ENV"] = "tier_0_smoke_pipeline"
    return env


def _run_status(tmp_path: Path, root: Path):
    return subprocess.run(
        [sys.executable, str(REPO / "run.py"), "--status", "--data-root", str(root)],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        timeout=60,
    )


def test_status_exits_zero_and_does_not_launch_wfa(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root)

    result = _run_status(tmp_path, root)

    assert result.returncode == 0, result.stderr
    assert "stage | stage_name" in result.stdout
    assert "WFA SPLIT PLAN" in result.stdout
    assert "[SPLIT" not in result.stdout
    assert "[RUN]" not in result.stdout
    assert not (tmp_path / "output/logs").exists()
    assert (tmp_path / "reports/validation/pipeline_flow_audit.csv").exists()
    assert (tmp_path / "reports/validation/pipeline_flow_audit.json").exists()


def test_status_reports_missing_target_clearly(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root, include_target=False)

    result = _run_status(tmp_path, root)

    assert result.returncode == 0, result.stderr
    assert "BASELINE FEATURE MATRIX" in result.stdout
    assert "target_15m_ret" in result.stdout
    assert "invalid" in result.stdout
    assert "missing required columns: target_15m_ret" in result.stdout


def test_status_reports_valid_baseline_checkpoint(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root)

    result = _run_status(tmp_path, root)

    assert result.returncode == 0, result.stderr
    baseline_lines = [line for line in result.stdout.splitlines() if "BASELINE FEATURE MATRIX" in line]
    assert baseline_lines
    assert "PASS" in baseline_lines[0]
    assert "valid" in baseline_lines[0]
    assert "target_15m_ret,target_valid" in baseline_lines[0] or "target_valid,target_15m_ret" in baseline_lines[0]


def test_status_configs_unchanged(monkeypatch):
    import pipeline.common.config as config_module

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
    assert p995.execution.threshold_mode == "prediction_abs_quantile"
    assert p995.execution.threshold_quantile == 0.995
    assert p999.execution.threshold_mode == "prediction_abs_quantile"
    assert p999.execution.threshold_quantile == 0.999
