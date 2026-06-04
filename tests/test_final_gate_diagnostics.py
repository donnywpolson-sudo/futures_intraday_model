import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.common.config import RootConfig
from pipeline.validation.final_gate_diagnostics import write_final_gate_diagnostics


def _stage25(path: Path) -> None:
    ts = [datetime(2025, 1, 1) + timedelta(minutes=i) for i in range(12)]
    df = pl.DataFrame(
        {
            "run_id": ["run_test"] * 12,
            "profile": ["tier_1_bare_minimum_alpha"] * 12,
            "symbol": ["ES"] * 6 + ["CL"] * 6,
            "split": ["1"] * 6 + ["1"] * 6,
            "timestamp": ts,
            "ts_event": ts,
            "prediction": [0.1] * 12,
            "target_15m_ret": [1.0] * 12,
            "position": [1, 1, 1, 1, 1, 1] + [0, 0, 0, 0, 0, 0],
            "position_after": [1, 1, 1, 1, 1, 1] + [0, 0, 0, 0, 0, 0],
            "position_delta": [1, 0, 0, 0, 0, 0] + [0, 0, 0, 0, 0, 0],
            "gross_pnl": [2.0] * 6 + [0.0] * 6,
            "costs": [0.1, 0, 0, 0, 0, 0] + [0.0] * 6,
            "pnl": [1.9, 2, 2, 2, 2, 2] + [0.0] * 6,
            "net_pnl": [1.9, 2, 2, 2, 2, 2] + [0.0] * 6,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def test_final_gate_breakdown_writes_one_row_per_final_symbol_split(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stage25 = Path("reports/validation/stage_25_final_oos_predictions.parquet")
    _stage25(stage25)

    result = write_final_gate_diagnostics(config=RootConfig(), run_id="run_test", profile="tier_1_bare_minimum_alpha", stage25_path=stage25, stage27_status="REJECT")

    rows = json.loads(Path("reports/validation/final_gate_breakdown.json").read_text())
    assert result["breakdown_rows"] == 2
    assert {(r["symbol"], r["split"]) for r in rows} == {("ES", "1"), ("CL", "1")}


def test_failed_gate_names_and_near_miss_profitable_reject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stage25 = Path("reports/validation/stage_25_final_oos_predictions.parquet")
    _stage25(stage25)

    write_final_gate_diagnostics(config=RootConfig(), run_id="run_test", profile="tier_1_bare_minimum_alpha", stage25_path=stage25, stage27_status="REJECT")
    breakdown = json.loads(Path("reports/validation/final_gate_breakdown.json").read_text())
    near = json.loads(Path("reports/validation/final_near_miss.json").read_text())

    es = next(r for r in breakdown if r["symbol"] == "ES")
    assert "min_trades" in es["failed_gates"]
    assert any(r["symbol"] == "ES" and r["profitable_reject"] is True for r in near)


def test_final_symbol_contribution_sums_to_final_totals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stage25 = Path("reports/validation/stage_25_final_oos_predictions.parquet")
    _stage25(stage25)

    write_final_gate_diagnostics(config=RootConfig(), run_id="run_test", profile="tier_1_bare_minimum_alpha", stage25_path=stage25, stage27_status="REJECT")
    contrib = json.loads(Path("reports/validation/final_symbol_contribution.json").read_text())
    df = pl.read_parquet(stage25)

    assert abs(sum(float(r["net_pnl"]) for r in contrib) - float(df["net_pnl"].sum())) < 1e-9
    assert abs(sum(float(r["gross_pnl"]) for r in contrib) - float(df["gross_pnl"].sum())) < 1e-9


def test_alpha_evidence_final_scope_reports_rejection_honestly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stage25 = Path("reports/validation/stage_25_final_oos_predictions.parquet")
    _stage25(stage25)

    write_final_gate_diagnostics(config=RootConfig(), run_id="run_test", profile="tier_1_bare_minimum_alpha", stage25_path=stage25, stage27_status="REJECT")
    alpha = json.loads(Path("reports/validation/alpha_evidence.json").read_text())
    row = next(r for r in alpha if r["stage_scope"] == "final")

    assert row["REJECT"] == 1
    assert row["ACCEPT"] == 0
    assert row["conclusion"] != "PASS_GATE_RESEARCH_READY"


def test_acceptance_thresholds_unchanged():
    cfg = RootConfig()

    assert cfg.acceptance_gate.min_oos_sharpe == 0.25
    assert cfg.acceptance_gate.min_trades == 30
    assert cfg.acceptance_gate.max_drawdown_pct == -0.20
