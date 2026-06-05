import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

from pipeline.validation.es_split_22_trace import (
    RAW_FORENSICS_JSON,
    ROBUST_ALPHA_JSON,
    TOP_BAR_TRACE_JSON,
    write_es_split_22_trace_diagnostics,
)


def _write_trace_artifacts() -> dict[str, Path]:
    Path("reports/validation").mkdir(parents=True, exist_ok=True)
    base = datetime(2025, 3, 22, tzinfo=timezone.utc)
    rows = []
    for split in ["21", "22", "23"]:
        for i in range(12):
            gap = 30 if split == "22" and i == 6 else i
            ts = base + timedelta(days=int(split) - 21, minutes=gap)
            net = 100.0 - i if split == "22" and i < 10 else -1.0
            rows.append(
                {
                    "run_id": "run_trace",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "symbol": "ES",
                    "split": split,
                    "timestamp": ts,
                    "ts_event": ts,
                    "open": 100.0 + i,
                    "high": 101.0 + i,
                    "low": 99.0 + i,
                    "close": 100.5 + i,
                    "volume": 100000.0 if split == "22" and i == 5 else 100.0 + i,
                    "target_15m_ret": 5.0 if split == "22" and i == 5 else 0.01 * i,
                    "prediction": 0.1,
                    "raw_signal": 1,
                    "position_after": 1,
                    "session_id": "s1" if i < 6 else "s2",
                    "session_date": "2025-03-22",
                    "costs": 1.0,
                    "net_pnl": net,
                    "feature_a": float(i),
                }
            )
    pl.DataFrame(rows).write_parquet("stage24.parquet")
    breakdown = []
    for split in ["21", "22", "23"]:
        breakdown.append(
            {
                "run_id": "run_trace",
                "profile": "tier_1_final_threshold_p999_experiment",
                "symbol": "ES",
                "split": split,
                "acceptance_status": "REJECT",
                "net_pnl": 900.0 if split == "22" else -10.0,
                "active_bar_pct": 0.05 if split == "22" else 0.0,
                "turnover": 400 if split == "22" else 1,
            }
        )
    Path("reports/validation/final_gate_breakdown.json").write_text(json.dumps(breakdown), encoding="utf-8")
    Path("features.json").write_text(json.dumps({"feature_cols": ["feature_a"]}), encoding="utf-8")
    roots = {}
    for stage in ["raw", "validated", "session_normalized", "causally_gated", "labeled", "feature_matrix"]:
        root = Path(stage)
        out = root / "ES"
        out.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(rows).filter(pl.col("split") == "22").drop("timestamp").write_parquet(out / "2025.parquet")
        roots[stage] = root
    return roots


def test_top_bar_trace_preserves_chronology(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    roots = _write_trace_artifacts()

    write_es_split_22_trace_diagnostics(
        run_id="run_trace",
        stage24_path="stage24.parquet",
        feature_cols_path="features.json",
        source_roots=roots,
    )
    rows = json.loads(TOP_BAR_TRACE_JSON.read_text(encoding="utf-8"))
    timestamps = [r["timestamp"] for r in rows]

    assert timestamps == sorted(timestamps)
    assert len(rows) == 10


def test_robust_alpha_evidence_computes_exclusion_math(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    roots = _write_trace_artifacts()

    write_es_split_22_trace_diagnostics(
        run_id="run_trace",
        stage24_path="stage24.parquet",
        feature_cols_path="features.json",
        source_roots=roots,
    )
    row = json.loads(ROBUST_ALPHA_JSON.read_text(encoding="utf-8"))[0]

    assert row["full_net_pnl"] == 880.0
    assert row["net_pnl_excluding_es_split_22"] == -20.0
    assert row["conclusion"] == "NO_ROBUST_ALPHA"


def test_raw_session_forensic_flags_gap_and_extreme_volume(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    roots = _write_trace_artifacts()

    write_es_split_22_trace_diagnostics(
        run_id="run_trace",
        stage24_path="stage24.parquet",
        feature_cols_path="features.json",
        source_roots=roots,
    )
    rows = json.loads(RAW_FORENSICS_JSON.read_text(encoding="utf-8"))

    assert any(r["missing_bar_gap_flag"] for r in rows)
    assert any(r["extreme_volume_flag"] for r in rows)


def test_diagnostics_are_run_scoped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    roots = _write_trace_artifacts()

    write_es_split_22_trace_diagnostics(
        run_id="run_trace",
        stage24_path="stage24.parquet",
        feature_cols_path="features.json",
        source_roots=roots,
    )
    rows = json.loads(RAW_FORENSICS_JSON.read_text(encoding="utf-8"))

    assert {r["run_id"] for r in rows} == {"run_trace"}


def test_no_strategy_config_changes():
    import yaml

    cfg_path = Path(__file__).resolve().parents[1] / "configs" / "alpha_tiered.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    prod = raw["base"]["execution"]
    p999 = raw["profiles"]["tier_1_final_threshold_p999_experiment"]["execution"]

    assert prod["threshold_mode"] == "fixed"
    assert prod["prediction_entry_threshold"] == 0.25
    assert p999["threshold_mode"] == "prediction_abs_quantile"
    assert p999["threshold_quantile"] == 0.999
