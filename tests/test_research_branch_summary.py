import json
from pathlib import Path

from pipeline.validation.research_branch_summary import SUMMARY_JSON, SUMMARY_MD, write_research_branch_summary


def _write_inputs() -> None:
    out = Path("reports/validation")
    out.mkdir(parents=True, exist_ok=True)
    (out / "pipeline_flow_audit.json").write_text(
        json.dumps(
            [
                {"stage_index": "1", "stage_name": "RAW DATA", "status": "PASS", "reason": "ok"},
                {"stage_index": "27", "stage_name": "STRATEGY ACCEPT / REJECT GATE", "status": "FAIL", "reason": "strategy gate rejected"},
            ]
        ),
        encoding="utf-8",
    )
    (out / "experiment_comparison.json").write_text(
        json.dumps([{"profile": "prod", "run_id": "run_b", "net_pnl": 10, "gross_pnl": 20, "ACCEPT": 0, "REJECT": 90}]),
        encoding="utf-8",
    )
    (out / "final_experiment_comparison.json").write_text(
        json.dumps(
            [
                {
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "run_id": "run_f",
                    "net_pnl": 100,
                    "gross_pnl": 120,
                    "cost_drag": 20,
                    "outlier_count": 1,
                    "ACCEPT": 0,
                    "REJECT": 90,
                }
            ]
        ),
        encoding="utf-8",
    )
    (out / "robust_alpha_evidence.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "run_f",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "full_net_pnl": 100,
                    "net_pnl_excluding_es_split_22": -5,
                    "net_pnl_excluding_threshold_outliers": -5,
                    "conclusion": "NO_ROBUST_ALPHA",
                }
            ]
        ),
        encoding="utf-8",
    )
    (out / "final_outlier_forensics.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "run_f",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "split": "22",
                    "net_pnl": 105,
                    "top_10_bar_pct_of_split_pnl": 0.82,
                    "missing_bar_gaps": 19,
                    "max_volume_zscore": 47,
                    "failed_gates": "min_oos_sharpe,max_drawdown_pct",
                }
            ]
        ),
        encoding="utf-8",
    )
    (out / "final_gate_pass_rates.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "run_f",
                    "profile": "tier_1_final_threshold_p999_experiment",
                    "gate": "min_trades",
                    "fail_count": 80,
                    "pass_rate": 0.111,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_research_branch_summary_writes_closure_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_inputs()

    result = write_research_branch_summary()
    rows = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    md = SUMMARY_MD.read_text(encoding="utf-8")

    assert rows[0]["final_conclusion"] == "NO_ROBUST_ALPHA"
    assert "target redesign" in rows[0]["recommended_next_research_directions"]
    assert "Stage 27 STRATEGY ACCEPT / REJECT GATE: FAIL" in md
    assert result["row"]["pipeline_fail_count"] == 1


def test_research_branch_summary_does_not_change_configs():
    import yaml

    raw = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs" / "alpha_tiered.yaml").read_text(encoding="utf-8"))

    prod = raw["base"]["execution"]
    p999 = raw["profiles"]["tier_1_final_threshold_p999_experiment"]["execution"]
    assert prod["threshold_mode"] == "fixed"
    assert prod["prediction_entry_threshold"] == 0.25
    assert p999["threshold_mode"] == "prediction_abs_quantile"
    assert p999["threshold_quantile"] == 0.999

