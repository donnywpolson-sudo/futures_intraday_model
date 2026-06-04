import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from pipeline.common.config import RootConfig
from pipeline.validation.final_trade_audit import write_final_trade_count_audit


def _stage25(path: Path) -> None:
    ts = [datetime(2025, 1, 1) + timedelta(minutes=i) for i in range(4)]
    df = pl.DataFrame(
        {
            "run_id": ["run_test"] * 8,
            "profile": ["tier_1_final_threshold_p999_experiment"] * 8,
            "symbol": ["ES"] * 4 + ["CL"] * 4,
            "split": ["1"] * 4 + ["1"] * 4,
            "timestamp": ts + ts,
            "ts_event": ts + ts,
            "prediction": [0.1] * 8,
            "target_15m_ret": [0.0] * 8,
            "position": [0, 1, -1, 0] + [0, 1, 1, 0],
            "position_after": [0, 1, -1, 0] + [0, 1, 1, 0],
            "position_delta": [0, 1, -2, 1] + [0, 1, 0, 1],
            "gross_pnl": [0, 5, 5, 5] + [0, 2, 2, 2],
            "net_pnl": [0, 4, 4, 4] + [0, 1, 1, 1],
            "pnl": [0, 4, 4, 4] + [0, 1, 1, 1],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def _breakdown() -> None:
    rows = [
        {
            "run_id": "run_test",
            "profile": "tier_1_final_threshold_p999_experiment",
            "symbol": "ES",
            "split": "1",
            "trade_count": 3,
            "turnover": 4,
            "net_pnl": 12,
            "gross_pnl": 15,
            "sharpe_annualized": 2.0,
            "max_drawdown_pct": -0.01,
            "profit_factor": 2.0,
            "acceptance_status": "REJECT",
            "failed_gates": "min_trades",
        },
        {
            "run_id": "run_test",
            "profile": "tier_1_final_threshold_p999_experiment",
            "symbol": "CL",
            "split": "1",
            "trade_count": 2,
            "turnover": 2,
            "net_pnl": 3,
            "gross_pnl": 6,
            "sharpe_annualized": 1.0,
            "max_drawdown_pct": -0.01,
            "profit_factor": 2.0,
            "acceptance_status": "REJECT",
            "failed_gates": "min_trades,min_oos_sharpe",
        },
        {"run_id": "other_run", "symbol": "ES", "split": "1", "trade_count": 999},
    ]
    path = Path("reports/validation/final_gate_breakdown.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_trade_count_audit_writes_one_row_per_final_symbol_split(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stage25(Path("reports/validation/stage_25_final_oos_predictions.parquet"))
    _breakdown()

    result = write_final_trade_count_audit(
        run_id="run_test",
        profile="tier_1_final_threshold_p999_experiment",
        config=RootConfig(),
    )
    rows = json.loads(Path("reports/validation/final_trade_count_audit.json").read_text())

    assert result["audit_rows"] == 2
    assert {(r["symbol"], r["split"]) for r in rows} == {("ES", "1"), ("CL", "1")}
    assert {r["run_id"] for r in rows} == {"run_test"}


def test_min_trades_near_miss_captures_profitable_rejects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stage25(Path("reports/validation/stage_25_final_oos_predictions.parquet"))
    _breakdown()

    write_final_trade_count_audit(
        run_id="run_test",
        profile="tier_1_final_threshold_p999_experiment",
        config=RootConfig(),
    )
    near = json.loads(Path("reports/validation/final_min_trades_near_miss.json").read_text())

    assert len(near) == 2
    assert near[0]["symbol"] == "ES"
    assert near[0]["trades_shortfall"] == 27
    assert near[0]["pnl_per_trade"] == 4.0


def test_flip_counting_matches_current_cost_turnover_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stage25(Path("reports/validation/stage_25_final_oos_predictions.parquet"))
    _breakdown()

    write_final_trade_count_audit(
        run_id="run_test",
        profile="tier_1_final_threshold_p999_experiment",
        config=RootConfig(),
    )
    rows = json.loads(Path("reports/validation/final_trade_count_audit.json").read_text())
    es = next(r for r in rows if r["symbol"] == "ES")

    assert es["position_change_events"] == 3
    assert es["trade_count_used_by_gate"] == 3
    assert es["position_turnover"] == 4.0
    assert es["flips_long_to_short"] == 1
    assert es["round_trip_count_estimate"] == 2
    assert "abs(delta)=2" in es["flip_cost_contract"]


def test_trade_audit_thresholds_and_profiles_unchanged():
    cfg = RootConfig()

    assert cfg.acceptance_gate.min_trades == 30
    assert cfg.acceptance_gate.min_oos_sharpe == 0.25
    assert cfg.acceptance_gate.max_drawdown_pct == -0.20
