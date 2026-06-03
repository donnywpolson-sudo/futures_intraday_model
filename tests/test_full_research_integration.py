import json
import os
import subprocess
import sys
from pathlib import Path

import polars as pl


REPO = Path(__file__).resolve().parents[1]


def _run_cli(args, cwd, extra_env=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["QUANT_MODELING_MODE"] = "full_research"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "pipeline.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _write_synthetic(path: Path) -> None:
    n = 220
    ts = pl.datetime_range(
        pl.datetime(2024, 1, 1, 9, 30),
        pl.datetime(2024, 1, 1, 13, 9),
        "1m",
        eager=True,
    )
    x = [((i % 11) - 5) / 5.0 for i in range(n)]
    target = [0.002 * x[i] + (0.0003 if i % 3 == 0 else -0.0002) for i in range(n)]
    df = pl.DataFrame(
        {
            "ts_event": ts,
            "open": [100.0 + i * 0.01 for i in range(n)],
            "high": [100.2 + i * 0.01 for i in range(n)],
            "low": [99.8 + i * 0.01 for i in range(n)],
            "close": [100.05 + i * 0.01 for i in range(n)],
            "volume": [1000 + (i % 17) for i in range(n)],
            "x_signal": x,
            "noise": [float((i * 7) % 13) for i in range(n)],
            "target_15m_ret": target,
        }
    )
    path.parent.mkdir(parents=True)
    df.write_parquet(path)


def test_full_research_cli_writes_all_artifacts_and_oos_is_strict(tmp_path):
    data = tmp_path / "data" / "ES" / "2024.parquet"
    _write_synthetic(data)
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "out_split_1"
    train_start = "2024-01-01T09:30:00"
    train_end = "2024-01-01T11:10:00"
    test_start = "2024-01-01T11:10:00"
    test_end = "2024-01-01T13:00:00"

    discover = _run_cli(["discover", "--data", str(data), "--out", str(manifest), "--start", train_start, "--end", train_end], tmp_path)
    assert discover.returncode == 0, discover.stderr
    run = _run_cli(
        [
            "run",
            "--data",
            str(data),
            "--manifest",
            str(manifest),
            "--out",
            str(out),
            "--train-start",
            train_start,
            "--train-end",
            train_end,
            "--start",
            test_start,
            "--end",
            test_end,
        ],
        tmp_path,
    )
    assert run.returncode == 0, run.stderr

    assert (out / "backtest_results.parquet").exists()
    assert (out / "oos_predictions.parquet").exists()
    assert (out / "execution_trace_report.json").exists()
    metrics = list((tmp_path / "reports" / "metrics").glob("*_metrics_report.json"))
    leakage = list((tmp_path / "reports" / "leakage").glob("*.json"))
    stress = list((tmp_path / "reports" / "stress").glob("*_stress_report.json"))
    acceptance = list((tmp_path / "reports" / "acceptance").glob("*_acceptance_gate.json"))
    assert metrics and leakage and stress and acceptance

    run_manifest = json.loads((tmp_path / "artifacts" / "run_manifests" / "out_split_1.json").read_text(encoding="utf-8"))
    split = run_manifest["splits"][0]
    selector = tmp_path / split["selector_artifact"]
    scaler = tmp_path / split["scaler_artifact"]
    assert selector.exists()
    assert scaler.exists()

    oos = pl.read_parquet(out / "oos_predictions.parquet")
    assert oos.height > 0
    assert oos["modeling_mode"].unique().to_list() == ["full_research"]
    assert "feature_set_id" in oos.columns
    assert oos.filter(pl.col("ts_event") < pl.datetime(2024, 1, 1, 11, 10)).is_empty()
    assert oos.filter(pl.col("ts_event") >= pl.datetime(2024, 1, 1, 13, 0)).is_empty()

    for key, value in run_manifest["audit_paths"].items():
        if key == "cli_command" or not value:
            continue
        assert (tmp_path / value).exists() if not Path(value).is_absolute() else Path(value).exists()
    for key in [
        "backtest_results",
        "oos_predictions",
        "leakage_report",
        "execution_trace_report",
        "metrics_report",
        "stress_report",
        "acceptance_report",
        "selector_artifact",
        "scaler_artifact",
    ]:
        value = split[key]
        assert (tmp_path / value).exists() if not Path(value).is_absolute() else Path(value).exists()
