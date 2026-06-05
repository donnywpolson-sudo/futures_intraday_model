import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

from pipeline.validation.final_outlier_forensics import (
    FORENSICS_JSON,
    NEIGHBOR_JSON,
    TRADES_JSON_TEMPLATE,
    write_final_outlier_forensics,
)


def _write_artifacts() -> None:
    Path("reports/validation").mkdir(parents=True, exist_ok=True)
    rows = []
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for split in ["21", "22", "23"]:
        for i in range(6):
            ts = base + timedelta(minutes=i + (int(split) - 21) * 100)
            if split == "22" and i == 3:
                ts = base + timedelta(minutes=2 + (int(split) - 21) * 100)  # duplicate
            pos = 1.0 if i in {1, 2, 3} else 0.0
            prior = 1.0 if i in {2, 3, 4} else 0.0
            rows.append(
                {
                    "run_id": "run_x",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "symbol": "ES",
                    "split": split,
                    "timestamp": ts,
                    "ts_event": ts,
                    "prediction_time": ts,
                    "execution_time": ts + timedelta(minutes=1),
                    "test_start": "2025-01-01",
                    "test_end": "2025-01-02",
                    "session_id": "s1",
                    "session_date": "2025-01-01",
                    "prediction": float(i) / 100.0,
                    "target_15m_ret": 0.01 * i,
                    "close": 100.0 + i,
                    "volume": 1000.0 + i,
                    "position_before": prior,
                    "position_after": pos,
                    "position_delta": pos - prior,
                    "gross_pnl": 100.0 if split == "22" and i == 2 else -1.0,
                    "costs": abs(pos - prior),
                    "net_pnl": 99.0 if split == "22" and i == 2 else -2.0,
                }
            )
    pl.DataFrame(rows).write_parquet("stage.parquet")
    breakdown = [
        {
            "run_id": "run_x",
            "profile": "tier_1_final_threshold_p999_experiment",
            "symbol": "ES",
            "split": split,
            "acceptance_status": "REJECT",
            "failed_gates": "min_trades",
            "net_pnl": 89.0 if split == "22" else -12.0,
            "gross_pnl": 94.0 if split == "22" else -6.0,
            "cost_drag": 5.0,
            "turnover": 4,
            "trade_count": 4,
            "active_bar_pct": 0.5,
            "sharpe_annualized": 1.0,
            "max_drawdown_pct": -0.3,
            "profit_factor": 1.2,
        }
        for split in ["21", "22", "23"]
    ]
    Path("reports/validation/final_gate_breakdown.json").write_text(json.dumps(breakdown), encoding="utf-8")


def test_outlier_forensic_report_writes_for_selected_split(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_artifacts()

    result = write_final_outlier_forensics(run_id="run_x", symbol="ES", split="22", stage_path="stage.parquet")
    rows = json.loads(FORENSICS_JSON.read_text(encoding="utf-8"))

    assert result["trade_rows"] > 0
    assert rows[0]["run_id"] == "run_x"
    assert rows[0]["symbol"] == "ES"
    assert rows[0]["split"] == "22"


def test_trade_extraction_preserves_chronological_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_artifacts()

    write_final_outlier_forensics(run_id="run_x", symbol="ES", split="22", stage_path="stage.parquet")
    trades = json.loads(Path(TRADES_JSON_TEMPLATE.format(symbol="ES", split="22")).read_text(encoding="utf-8"))
    timestamps = [r["timestamp"] for r in trades]

    assert timestamps == sorted(timestamps)


def test_concentration_metrics_compute_correctly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_artifacts()

    write_final_outlier_forensics(run_id="run_x", symbol="ES", split="22", stage_path="stage.parquet")
    row = json.loads(FORENSICS_JSON.read_text(encoding="utf-8"))[0]

    assert row["top_1_bar_pnl"] == 99.0
    assert row["bars_for_80pct_pnl"] == 1


def test_data_sanity_flags_duplicate_timestamps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_artifacts()

    write_final_outlier_forensics(run_id="run_x", symbol="ES", split="22", stage_path="stage.parquet")
    row = json.loads(FORENSICS_JSON.read_text(encoding="utf-8"))[0]

    assert row["duplicate_timestamps"] > 0


def test_neighbor_comparison_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_artifacts()

    write_final_outlier_forensics(run_id="run_x", symbol="ES", split="22", stage_path="stage.parquet")
    rows = json.loads(NEIGHBOR_JSON.read_text(encoding="utf-8"))

    assert {r["split"] for r in rows} == {"21", "22", "23"}
