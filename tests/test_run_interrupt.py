import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.common.config import DataSectionConfig, RootConfig
from pipeline.data_gate.manifest import build_data_manifest


REPO = Path(__file__).resolve().parents[1]


def _write_baseline(root: Path, n: int = 1500) -> None:
    start = datetime(2025, 1, 1, 9, 30)
    df = pl.DataFrame({
        "ts_event": [start + timedelta(hours=4 * i) for i in range(n)],
        "open": [5000.0 + i for i in range(n)],
        "high": [5001.0 + i for i in range(n)],
        "low": [4999.0 + i for i in range(n)],
        "close": [5000.5 + i for i in range(n)],
        "volume": [100 + i for i in range(n)],
        "x": [float(i % 11) for i in range(n)],
        "target_valid": [True] * n,
        "target_15m_ret": [0.01 if i % 2 else -0.01 for i in range(n)],
    })
    p = root / "ES" / "2025.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)
    (root / "column_registry.json").write_text(
        '{"feature_columns":["x"],"target_columns":["target_15m_ret"]}',
        encoding="utf-8",
    )
    build_data_manifest(root, stage="baseline_feature_matrix")


def _interrupt_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["CONFIG_ENV"] = "tier_0_smoke_pipeline"
    env["QUANT_MODELING_MODE"] = "minimal_compatible"
    env["QUANT_TEST_INTERRUPT_AT"] = "before_loop"
    return env


def test_top_level_keyboard_interrupt_exits_130_and_writes_artifacts(tmp_path):
    root = tmp_path / "data/feature_matrices/baseline"
    _write_baseline(root)

    result = subprocess.run(
        [sys.executable, str(REPO / "run.py"), "--from-stage", "baseline_feature_matrix", "--data-root", str(root)],
        cwd=tmp_path,
        env=_interrupt_env(),
        text=True,
        capture_output=True,
        timeout=90,
    )
    out = result.stdout + result.stderr

    assert result.returncode == 130
    assert "RUN INTERRUPTED: user/system interrupted" in out
    assert "deployment=NOT_READY mode=interrupted" in out
    assert "resume_command=python run.py --from-stage baseline_feature_matrix --data-root data\\feature_matrices\\baseline" in out
    assert "object type name:" not in out
    assert "lost sys.stderr" not in out
    assert "[FINAL SAFETY SUMMARY]" not in out

    payload = json.loads((tmp_path / "reports/validation/run_interrupted.json").read_text(encoding="utf-8"))
    assert payload["reason"] == "KeyboardInterrupt"
    assert payload["run_id"].startswith("run_")
    assert payload["start_stage"] == "baseline_feature_matrix"
    assert payload["checkpoint_mode"] == "True"
    assert (tmp_path / "reports/validation/run_interrupted.csv").exists()


def test_child_process_is_terminated_on_keyboard_interrupt(monkeypatch):
    import run

    class _Stream:
        def readline(self):
            return ""

    class _Proc:
        stdout = _Stream()
        stderr = _Stream()
        returncode = None

        def __init__(self):
            self.terminated = False
            self.killed = False

        def wait(self, timeout=None):
            if not self.terminated:
                raise KeyboardInterrupt()
            self.returncode = -15
            return self.returncode

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    proc = _Proc()
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **k: proc)

    try:
        run._run_subprocess_streaming([sys.executable, "-c", "pass"], os.environ.copy(), timeout_idle=999)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected KeyboardInterrupt")

    assert proc.terminated is True
    assert run._LAST_CHILD_INTERRUPT["returncode"] == -15


def test_completed_split_diagnostics_preserved_when_marking_interrupted(tmp_path, monkeypatch):
    import run

    monkeypatch.chdir(tmp_path)
    run._VERIFICATION_TABLE.clear()
    run._RUN_SPLIT_ARTIFACTS.clear()
    root = tmp_path / "data/feature_matrices/baseline/ES"
    p = root / "2025.parquet"
    p.parent.mkdir(parents=True)
    p.write_text("placeholder", encoding="utf-8")

    cfg = RootConfig(symbols=["ES"], data=DataSectionConfig(root=str(root.parent)))
    split1 = ([2025], [2025], None, None, None, None)
    split2 = ([2025], [2025], None, None, None, None)
    run._record_split_result({"symbol": "ES", "split": 1, "status": "OK", "path": "done"})

    counts = run._mark_interrupted_pending(cfg, [split1, split2], [p])

    assert counts["completed_splits"] == 1
    assert counts["pending_splits"] == 1
    by_split = {int(r["split"]): r for r in run._VERIFICATION_TABLE}
    assert by_split[1]["status"] == "OK"
    assert by_split[2]["status"] == "INTERRUPTED"


def test_production_threshold_unchanged_without_interrupt(monkeypatch):
    import pipeline.common.config as config_module

    monkeypatch.delenv("CONFIG_ENV", raising=False)
    monkeypatch.delenv("QUANT_ENV", raising=False)
    config_module._LOADED = False
    cfg = config_module.load_config("tier_1_bare_minimum_alpha")

    assert cfg.execution.threshold_mode == "fixed"
    assert cfg.execution.prediction_entry_threshold == 0.25
