from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts.build_metric_visualizations import exclusive_blocker_counts


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_metric_visualizations.py"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_fixture(tmp_path: Path, *, missing_optional: bool = False, missing_source: bool = False) -> Path:
    reports = tmp_path / "reports"
    inventory = reports / "report_inventory.json"
    charts = [
        {
            "chart": "Locked Tier 1 costed OOS summary cards",
            "status": "feasible",
            "sources": [
                "reports/phase8/alpha_promotion_decision.json",
                "reports/metrics/tier1_locked_baseline_20260616_metrics.json",
            ],
            "notes": "fixture",
        },
        {
            "chart": "net/gross/cost by market",
            "status": "feasible",
            "sources": ["reports/phase8/alpha_promotion_decision.json"],
            "notes": "fixture",
        },
        {
            "chart": "promotion gate blockers",
            "status": "feasible",
            "sources": ["reports/phase8/alpha_promotion_decision.json"],
            "notes": "fixture",
        },
        {
            "chart": "artifact provenance/readiness summary",
            "status": "feasible",
            "sources": [
                "reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json",
                "reports/model_selection/model_selection_report.json",
            ],
            "notes": "fixture",
        },
        {
            "chart": "Feature and target hypothesis statuses",
            "status": "feasible",
            "sources": [
                "manifests/feature_hypotheses/registry.json",
                "manifests/target_hypotheses/registry.json",
            ],
            "notes": "fixture",
        },
        {
            "chart": "Phase 9 stopped/rejected branch summary",
            "status": "feasible",
            "sources": [
                "reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md",
                "reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md",
                "reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.json",
                "reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.json",
            ],
            "notes": "fixture",
        },
        {
            "chart": "Equity curve / cumulative PnL over time",
            "status": "skipped",
            "sources": [],
            "notes": "not source-of-truth",
        },
        {
            "chart": "Live execution/fill/slippage dashboard",
            "status": "skipped",
            "sources": ["configs/costs.yaml"],
            "notes": "no live fill model",
        },
    ]
    source_files = [
        {"path": "reports/phase8/alpha_promotion_decision.json", "role": "phase8"},
        {"path": "reports/metrics/tier1_locked_baseline_20260616_metrics.json", "role": "metrics"},
        {"path": "reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json", "role": "wfa"},
        {"path": "reports/model_selection/model_selection_report.json", "role": "model_selection"},
        {"path": "manifests/feature_hypotheses/registry.json", "role": "feature_registry"},
        {"path": "manifests/target_hypotheses/registry.json", "role": "target_registry"},
        {"path": "reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md", "role": "audit"},
        {"path": "reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md", "role": "audit"},
        {"path": "reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.json", "role": "audit"},
        {"path": "reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.json", "role": "audit"},
    ]
    if missing_source:
        source_files.append({"path": "reports/missing_required.json", "role": "missing"})
    _write_json(
        inventory,
        {
            "schema_version": 1,
            "feasibility_verdict": "build partial dashboard",
            "charts": charts,
            "source_of_truth_report_files": source_files,
        },
    )
    phase8 = {
        "run": "fixture_run",
        "promoted": False,
        "blockers": ["net_return_dollars -1 below minimum 1.0", "cost_drag_to_abs_gross 2 above maximum 1.0"],
        "costed_oos": {
            "row_count": 10,
            "trade_count": 2,
            "gross_return_dollars": -5.0,
            "cost_dollars": 4.0,
            "net_return_dollars": -9.0,
            "slippage_cost_dollars": 3.0,
            "commission_cost_dollars": 1.0,
            "long_count": 1,
            "short_count": 1,
            "flat_count": 8,
            "net_sharpe_like": -1.0,
            "cost_drag_to_abs_gross": 0.8,
        },
        "markets": [
            {"market": "ES", "trade_count": 1, "gross_return_dollars": 2.0, "cost_dollars": 1.0, "net_return_dollars": 1.0},
            {"market": "CL", "trade_count": 1, "gross_return_dollars": -7.0, "cost_dollars": 3.0, "net_return_dollars": -10.0},
            {"market": "ZN", "trade_count": 0, "gross_return_dollars": 0.0, "cost_dollars": 0.0, "net_return_dollars": 0.0},
        ],
        "folds": [
            {"fold_id": "ES_0001", "trade_count": 1, "gross_return_dollars": 2.0, "cost_dollars": 1.0, "net_return_dollars": 1.0},
            {"fold_id": "CL_0001", "trade_count": 1, "gross_return_dollars": -7.0, "cost_dollars": 3.0, "net_return_dollars": -10.0},
        ],
        "warnings": [],
    }
    if missing_optional:
        phase8.pop("markets")
    _write_json(reports / "phase8" / "alpha_promotion_decision.json", phase8)
    _write_json(
        reports / "metrics" / "tier1_locked_baseline_20260616_metrics.json",
        {"research_alpha_ready": False, "model_promotion_allowed": False, "failure_count": 0},
    )
    _write_json(
        reports / "wfa" / "tier1_locked_baseline_20260616_predictions_manifest.json",
        {"run": "fixture_run", "artifact_evidence_ready": True, "failure_count": 0},
    )
    _write_json(
        reports / "model_selection" / "model_selection_report.json",
        {
            "selection_status": "NOT_SELECTED",
            "model_promotion_allowed": False,
            "failure_count": 0,
            "final_holdout_excluded_from_selection": True,
        },
    )
    _write_json(
        tmp_path / "manifests" / "feature_hypotheses" / "registry.json",
        {"hypotheses": [{"hypothesis_id": "baseline", "status": "FROZEN", "wfa_allowed": True, "feature_family": "base"}]},
    )
    _write_json(
        tmp_path / "manifests" / "target_hypotheses" / "registry.json",
        {"hypotheses": [{"target_hypothesis_id": "target", "status": "REJECTED", "wfa_allowed": False, "target_family": "path"}]},
    )
    _write_text(
        reports / "pipeline_audit" / "phase9_cost_clearability_harness_audit_20260617.md",
        "- Decision: `STOP_BRANCH_PERMANENTLY`\n",
    )
    _write_text(
        reports / "pipeline_audit" / "phase9_market_balanced_cost_clearability_harness_audit_20260617.md",
        "- Decision: `STOP_BRANCH_PERMANENTLY`\n",
    )
    _write_json(
        reports / "pipeline_audit" / "liquidity_cost_state_features_v1_smoke_20260617T045008Z.json",
        {"decision": "REJECTED"},
    )
    _write_json(
        reports / "pipeline_audit" / "directional_path_quality_target_v1_smoke_20260617T095912Z.json",
        {"decision": "STOP_UNDERPOWERED"},
    )
    return inventory


def _run_dashboard(tmp_path: Path, inventory: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reports-dir",
            str(tmp_path / "reports"),
            "--out-dir",
            str(tmp_path / "reports" / "visualizations"),
            "--inventory",
            str(inventory),
            *extra,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_script_runs_and_creates_dashboard_manifest_and_png(tmp_path: Path) -> None:
    inventory = _make_fixture(tmp_path)

    result = _run_dashboard(tmp_path, inventory)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "reports" / "visualizations" / "dashboard.html").exists()
    manifest_path = tmp_path / "reports" / "visualizations" / "visualization_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["charts_generated"]
    chart_names = {row["name"] for row in manifest["charts_generated"]}
    assert "Cost Components" in chart_names
    assert "Active Signal / Directional Balance" in chart_names
    assert "Non-Exclusive Policy Blocker Counts" in chart_names
    assert list((tmp_path / "reports" / "visualizations" / "charts").glob("*.png"))
    assert any(row["name"] == "Equity curve / cumulative PnL over time" for row in manifest["charts_skipped"])
    dashboard = (tmp_path / "reports" / "visualizations" / "dashboard.html").read_text(encoding="utf-8")
    assert "Alpha evidence" in dashboard
    assert "Deterministic next-action recommendations" in dashboard
    assert "Missing evidence" in dashboard
    assert "Active signal rows" in dashboard
    assert ">Trade count<" not in dashboard
    assert "zero_trade_market" in dashboard
    contract = json.loads((tmp_path / "reports" / "visualizations" / "dashboard_metric_contract.json").read_text(encoding="utf-8"))
    assert contract["missing_evidence"]
    missing_ids = {row["metric_id"] for row in contract["missing_evidence"]}
    assert "benchmark.random_sign_same_frequency" in missing_ids
    assert "benchmark.naive_momentum" in missing_ids
    assert "benchmark.naive_mean_reversion" in missing_ids
    assert "bootstrap.daily_net_expectancy_ci" in missing_ids
    assert "prop_firm.full_execution_realism" in missing_ids
    assert "research.feature_label_wfa_readiness" in missing_ids
    assert "validation.purge_embargo_leakage_dashboard_evidence" in missing_ids
    assert "risk.loss_limit_stress" in missing_ids
    missing_by_id = {row["metric_id"]: row for row in contract["missing_evidence"]}
    assert missing_by_id["live.fills_latency_capacity"]["stage"] == "future_live"
    assert missing_by_id["live.fills_latency_capacity"]["current_research_blocker"] is False
    assert missing_by_id["prop_firm.full_execution_realism"]["stage"] == "future_live"
    assert missing_by_id["holdout.final_performance"]["stage"] == "future_holdout"
    assert missing_by_id["benchmark.random_sign_same_frequency"]["current_research_blocker"] is True
    contract_ids = {row["id"] for row in contract["metrics"]}
    assert set(manifest["displayed_metric_ids"]).issubset(contract_ids)
    assert contract["run"] == "fixture_run"
    by_id = {row["id"]: row for row in contract["metrics"]}
    assert by_id["portfolio.gross_pnl"]["value"] - by_id["portfolio.total_costs"]["value"] == by_id["portfolio.net_pnl"]["value"]
    assert by_id["portfolio.daily_sharpe"]["formula"] == "mean(daily_net)/std(daily_net)*sqrt(252)"
    assert by_id["portfolio.daily_sortino"]["formula"] == "mean(daily_net)/std(negative_daily_net)*sqrt(252)"
    assert by_id["portfolio.net_pnl"]["promotion_metric"] is True
    assert by_id["portfolio.net_pnl"]["oos_only"] is True
    audit = (tmp_path / "reports" / "visualizations" / "dashboard_metric_audit.md").read_text(encoding="utf-8")
    assert "Dashboard Metric Audit" in audit


def test_missing_optional_fields_warn_but_do_not_crash(tmp_path: Path) -> None:
    inventory = _make_fixture(tmp_path, missing_optional=True)

    result = _run_dashboard(tmp_path, inventory)

    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((tmp_path / "reports" / "visualizations" / "visualization_manifest.json").read_text(encoding="utf-8"))
    assert any("market net chart skipped" in warning for warning in manifest["warnings"])
    assert (tmp_path / "reports" / "visualizations" / "dashboard.html").exists()


def test_fast_mode_skips_locked_prediction_derivation(tmp_path: Path) -> None:
    inventory = _make_fixture(tmp_path)

    result = _run_dashboard(tmp_path, inventory, "--fast")

    assert result.returncode == 0, result.stdout + result.stderr
    contract = json.loads((tmp_path / "reports" / "visualizations" / "dashboard_metric_contract.json").read_text(encoding="utf-8"))
    missing_by_id = {row["metric_id"]: row for row in contract["missing_evidence"]}
    assert missing_by_id["prediction.locked_oos_policy_frame"]["reason"] == "Fast dashboard mode skipped locked prediction-parquet derivation."
    assert missing_by_id["prediction.locked_oos_policy_frame"]["current_research_blocker"] is False


def test_strict_mode_fails_when_source_of_truth_file_is_missing(tmp_path: Path) -> None:
    inventory = _make_fixture(tmp_path, missing_source=True)

    result = _run_dashboard(tmp_path, inventory, "--strict")

    assert result.returncode != 0
    assert "missing source-of-truth file" in result.stdout


def test_exclusive_blocker_counts_sum_to_total_rows() -> None:
    frame = pd.DataFrame(
        {
            "position": [0, 0, 0, 1],
            "no_direction_signal": [True, False, False, False],
            "blocked_by_flat_probability": [False, True, True, False],
            "blocked_by_trend_danger": [False, True, False, False],
            "blocked_by_fade_filter": [False, False, True, False],
        }
    )

    counts = exclusive_blocker_counts(frame)

    assert sum(counts.values()) == len(frame)
    assert counts["no_direction_signal"] == 1
    assert counts["flat_probability_block"] == 2
    assert counts["trade_or_active"] == 1
