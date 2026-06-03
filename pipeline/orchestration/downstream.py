from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.cli import cmd_discover, cmd_run
from pipeline.common.io_safe import atomic_write_json
from pipeline.data_gate.checkpoint import validate_checkpoint_stage
from pipeline.features.baseline import baseline_feature_root
from pipeline.features.expansion import expanded_feature_root
from pipeline.labels.generate import label_root
from pipeline.orchestration.stage_plan import build_stage_plan


def _first_file(root: str | Path) -> Path:
    files = sorted(Path(root).glob("*/*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parquet files under {root}")
    return files[0]


def _bounds(path: Path) -> tuple[Any, Any, Any, Any]:
    df = pl.read_parquet(path).sort("ts_event")
    n = df.height
    if n < 4:
        raise ValueError("need at least 4 rows for checkpoint downstream smoke")
    train_start = df["ts_event"][0]
    train_end = df["ts_event"][max(1, n // 2)]
    test_start = train_end
    test_end = df["ts_event"][-1]
    return train_start, train_end, test_start, test_end


def _run_wfa(root: str | Path, config: Any, context: dict[str, Any], out_dir: str = "output/checkpoint_run") -> dict:
    data = _first_file(root)
    train_start, train_end, test_start, test_end = _bounds(data)
    manifest = Path(out_dir) / "discovery_manifest.json"
    cmd_discover(argparse.Namespace(data=str(data), out=str(manifest), start=str(train_start), end=str(train_end)))
    cmd_run(argparse.Namespace(data=str(data), manifest=str(manifest), out=out_dir, train_start=str(train_start), train_end=str(train_end), start=str(test_start), end=str(test_end), from_stage=None, data_root=None), hmm=False)
    return {
        "backtest_results": str(Path(out_dir) / "backtest_results.parquet"),
        "oos_predictions": str(Path(out_dir) / "oos_predictions.parquet"),
        "metrics_dir": "reports/metrics",
        "acceptance_dir": "reports/acceptance",
    }


def run_from_causally_gated_checkpoint(root, config, context) -> dict:
    gate = validate_checkpoint_stage("causally_gated_normalized", str(root), config, config.symbols, config.start_year, config.end_year)
    if gate["status"] != "PASS":
        raise RuntimeError(f"CHECKPOINT GATE FAIL: stage=causally_gated_normalized root={root} reason={'; '.join(gate['failures'][:3])}")
    plan = build_stage_plan("causally_gated_normalized", config)
    label = label_root(root, "data/labeled", config)
    baseline = baseline_feature_root("data/labeled", "data/feature_matrices/baseline", config)
    expanded = expanded_feature_root("data/feature_matrices/baseline", "data/feature_matrices/expanded", config)
    wfa = _run_wfa(root, config, context)
    payload = {"status": "PASS", "start_stage": "causally_gated_normalized", "stage_plan": plan, "checkpoint_gate": gate, "labels": label, "baseline": baseline, "expanded": expanded, "wfa": wfa}
    atomic_write_json("artifacts/run_manifests/checkpoint_downstream.json", payload)
    return payload


def run_from_session_normalized_checkpoint(root, config, context) -> dict:
    from pipeline.causal.gate import causal_gate_root

    gate = validate_checkpoint_stage("session_normalized", str(root), config, config.symbols, config.start_year, config.end_year)
    if gate["status"] != "PASS":
        raise RuntimeError(f"CHECKPOINT GATE FAIL: stage=session_normalized root={root} reason={'; '.join(gate['failures'][:3])}")
    causal_gate_root(root, "data/causally_gated_normalized")
    return run_from_causally_gated_checkpoint("data/causally_gated_normalized", config, context)


def run_from_labeled_checkpoint(root, config, context) -> dict:
    gate = validate_checkpoint_stage("labeled", str(root), config, config.symbols, config.start_year, config.end_year)
    if gate["status"] != "PASS":
        raise RuntimeError(f"CHECKPOINT GATE FAIL: stage=labeled root={root} reason={'; '.join(gate['failures'][:3])}")
    baseline = baseline_feature_root(root, "data/feature_matrices/baseline", config)
    expanded = expanded_feature_root("data/feature_matrices/baseline", "data/feature_matrices/expanded", config)
    return {"status": "PASS", "baseline": baseline, "expanded": expanded}


def run_from_baseline_matrix_checkpoint(root, config, context) -> dict:
    gate = validate_checkpoint_stage("baseline_feature_matrix", str(root), config, config.symbols, config.start_year, config.end_year)
    if gate["status"] != "PASS":
        raise RuntimeError(f"CHECKPOINT GATE FAIL: stage=baseline_feature_matrix root={root} reason={'; '.join(gate['failures'][:3])}")
    return _run_wfa(root, config, context)
