import json
from pathlib import Path

from pipeline.validation.frozen_set_comparison import FROZEN_SET_COMPARISON_JSON, write_frozen_set_comparison


def _write_inputs(tmp_path: Path) -> None:
    (tmp_path / "reports/validation").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/frozen_features/phase5_v1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/frozen_features/phase5_v1/feature_cols.json").write_text(
        json.dumps({"feature_cols": ["a", "b", "c"]}),
        encoding="utf-8",
    )
    (tmp_path / "reports/validation/final_threshold_profile_comparison.json").write_text(
        json.dumps(
            [
                {
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "run_id": "run_current",
                    "gross_pnl": 100.0,
                    "net_pnl": 80.0,
                    "cost_drag": 20.0,
                    "cost_drag_pct_of_gross": 0.2,
                    "total_turnover": 5.0,
                    "active_splits": 2,
                    "median_active_bar_pct": 0.01,
                    "ACCEPT": 0,
                    "REJECT": 90,
                    "WARN": 0,
                    "MISSING": 0,
                    "outlier_count": 0,
                    "profitable_min_trades_rejects": 1,
                    "median_min_trades_shortfall": 4,
                    "best_symbol_by_net_pnl": "ES",
                    "worst_symbol_by_net_pnl": "ZN",
                    "conclusion": "WEAK_ALPHA_RESEARCH_ONLY",
                },
                {
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "run_id": "run_old",
                    "gross_pnl": 90.0,
                    "net_pnl": 70.0,
                    "cost_drag": 20.0,
                    "cost_drag_pct_of_gross": 0.22,
                    "total_turnover": 4.0,
                    "active_splits": 1,
                    "median_active_bar_pct": 0.001,
                    "ACCEPT": 1,
                    "REJECT": 89,
                    "WARN": 0,
                    "MISSING": 0,
                    "outlier_count": 0,
                    "profitable_min_trades_rejects": 36,
                    "median_min_trades_shortfall": 17,
                    "best_symbol_by_net_pnl": "CL",
                    "worst_symbol_by_net_pnl": "ZN",
                    "conclusion": "WEAK_ALPHA_RESEARCH_ONLY",
                },
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "reports/validation/stage_24_final_wfa_backtest_results.parquet.lineage.json").write_text(
        json.dumps(
            {
                "run_id": "run_current",
                "profile": "tier_1_final_threshold_p999_experiment",
                "frozen_feature_manifest_hash": "hash_current",
                "selected_feature_count": 3,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "reports/validation/stage_27_strategy_acceptance_audit_report.json").write_text(
        json.dumps({"run_id": "run_current", "strategy_acceptance_status": "REJECT"}),
        encoding="utf-8",
    )
    (tmp_path / "reports/validation/final_min_trades_near_miss.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "run_current",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "symbol": "ES",
                    "split": "1",
                    "net_pnl": 12.5,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_frozen_set_comparison_groups_by_manifest_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_inputs(tmp_path)

    summary = write_frozen_set_comparison(current_run_id="run_current")
    rows = json.loads(FROZEN_SET_COMPARISON_JSON.read_text(encoding="utf-8"))
    current = next(r for r in rows if r["run_id"] == "run_current")

    assert current["frozen_manifest_hash"] == "hash_current"
    assert summary["best_net_pnl_run"] == "run_current"


def test_frozen_set_comparison_handles_missing_historical_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_inputs(tmp_path)

    write_frozen_set_comparison(current_run_id="run_current")
    old = next(r for r in json.loads(FROZEN_SET_COMPARISON_JSON.read_text(encoding="utf-8")) if r["run_id"] == "run_old")

    assert old["frozen_manifest_hash"] == ""
    assert old["artifact_available"] is False
    assert "prior artifact unavailable" in old["reason_if_missing"]


def test_selected_feature_count_and_stage27_status_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_inputs(tmp_path)

    write_frozen_set_comparison(current_run_id="run_current")
    current = next(r for r in json.loads(FROZEN_SET_COMPARISON_JSON.read_text(encoding="utf-8")) if r["run_id"] == "run_current")

    assert current["selected_feature_count"] == 3
    assert current["selected_features"] == "a,b,c"
    assert current["final_gate_status"] == "FAIL"
    assert current["artifact_available"] is True
    assert current["alpha_conclusion"] == "WEAK_ALPHA_RESEARCH_ONLY"


def test_production_config_not_changed_by_comparison(monkeypatch):
    import pipeline.common.config as config_module

    config_module._LOADED = False
    prod = config_module.load_config("tier_1_bare_minimum_alpha")

    assert prod.execution.threshold_mode == "fixed"
    assert prod.execution.prediction_entry_threshold == 0.25
