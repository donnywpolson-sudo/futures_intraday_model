from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.phase8_model_selection.candidate_failure_autopsy import (
    AutopsyPaths,
    run_autopsy,
)


HYPOTHESIS_ID = "fixture_candidate_v1"
RUN_ID = "fixture_candidate_v1_model_expansion_s1"


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _paths(tmp_path: Path) -> AutopsyPaths:
    return AutopsyPaths(
        target_smoke_root=tmp_path / "reports" / "pipeline_audit",
        wfa_manifest=tmp_path / "reports" / "wfa" / "manifest.json",
        wfa_report=tmp_path / "reports" / "wfa" / "report.json",
        policy_diagnostics=tmp_path / "reports" / "policy" / "diagnostics.json",
        policy_summary=tmp_path / "reports" / "policy" / "summary.csv",
        trades=tmp_path / "reports" / "policy" / "trades.csv",
        bars=tmp_path / "data" / "bars.parquet",
        costs_config=tmp_path / "configs" / "costs.yaml",
        first_touch_diagnostics=tmp_path / "reports" / "first_touch" / "diagnostics.json",
        first_touch_grid=tmp_path / "reports" / "first_touch" / "grid.csv",
        json_out=tmp_path / "reports" / "candidate_failure_autopsy" / "autopsy.json",
        md_out=tmp_path / "docs" / "fixture_candidate_v1_failure_autopsy.md",
    )


def _write_smokes(paths: AutopsyPaths) -> None:
    for stage, decision, top_net in (
        ("discovery", "DISCOVERY_PASS", 1000.0),
        ("confirmation", "CONFIRMATION_PASS", 1200.0),
        ("locked", "LOCKED_PASS", 1400.0),
    ):
        _write_json(
            paths.target_smoke_root
            / f"es_30m_target_smoke_{HYPOTHESIS_ID}_{stage}_smoke.json",
            {
                "decision": decision,
                "failure_count": 0,
                "stage_summary": {
                    "scored_rows": 100,
                    "top_rows": 5,
                    "top_total_net_dollars": top_net,
                    "positive_top_net_fold_count": 4,
                },
                "gates": [
                    {
                        "gate": "not_duplicate_of_current_15m_deadzone",
                        "pass": True,
                        "overlap": 0.40,
                    }
                ],
            },
        )


def _write_core_artifacts(paths: AutopsyPaths) -> None:
    _write_smokes(paths)
    _write_json(
        paths.wfa_manifest,
        {
            "failure_count": 0,
            "prediction_count": 100,
            "fold_count": 2,
            "model_ids": ["fixture_model"],
            "target_names": ["target_sign_with_deadzone"],
            "prediction_markets": ["ES"],
            "prediction_years": [2024],
            "duplicate_prediction_count": 0,
            "artifact_evidence_ready": True,
        },
    )
    _write_json(paths.wfa_report, {"model_risk_gate": {"status": "PASS_METADATA_READY"}})
    _write_json(
        paths.policy_diagnostics,
        {
            "failure_count": 0,
            "coverage": {"row_count": 100},
            "trade_count": 2,
            "candidate_trade_count": 90,
            "blocked_by_execution_overlap": 88,
            "gross_return_dollars": -15.0,
            "cost_dollars": 20.0,
            "net_return_dollars": -35.0,
            "fixed_exit_policy_mismatch": True,
            "target_policy_compatibility": {"compatible": False},
            "policy_metrics": {
                "fold": {
                    "ES_research_0001": {"net_return_dollars": 15.0},
                    "ES_research_0002": {"net_return_dollars": -60.0},
                }
            },
        },
    )
    paths.policy_summary.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "scope": "overall",
                "scope_value": "all",
                "row_count": 100,
                "trade_count": 2,
                "candidate_trade_count": 90,
                "blocked_by_execution_overlap": 88,
                "gross_return_dollars": -15.0,
                "cost_dollars": 20.0,
                "net_return_dollars": -35.0,
            },
            {
                "scope": "fold",
                "scope_value": "ES_research_0001",
                "trade_count": 1,
                "gross_return_dollars": 25.0,
                "cost_dollars": 10.0,
                "net_return_dollars": 15.0,
            },
            {
                "scope": "fold",
                "scope_value": "ES_research_0002",
                "trade_count": 1,
                "gross_return_dollars": -50.0,
                "cost_dollars": 10.0,
                "net_return_dollars": -60.0,
            },
        ]
    ).to_csv(paths.policy_summary, index=False)
    paths.costs_config.parent.mkdir(parents=True, exist_ok=True)
    paths.costs_config.write_text(
        """
markets:
  ES:
    tick_size: 0.25
    tick_value: 12.5
    round_turn_cost_dollars: 10.0
""".strip(),
        encoding="utf-8",
    )
    _write_json(
        paths.first_touch_diagnostics,
        {
            "decision_support": {
                "screen_status": "FIRST_TOUCH_FEASIBILITY_NO_GO",
                "grid_count": 1,
                "fold_count": 2,
                "stop_first_positive_overall_grid_count": 0,
                "ambiguous_excluded_positive_overall_grid_count": 0,
                "stop_first_at_least_3_positive_fold_grid_count": 0,
            },
            "cost_model": {"tick_value": 12.5},
            "overall_grid_summary": [
                {
                    "take_profit_ticks": 4,
                    "stop_loss_ticks": 4,
                    "stop_first_net_dollars": -25.0,
                }
            ],
        },
    )
    paths.first_touch_grid.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"take_profit_ticks": 4, "stop_loss_ticks": 4, "stop_first_net_dollars": -25.0}]
    ).to_csv(paths.first_touch_grid, index=False)


def _write_trades_and_bars(paths: AutopsyPaths) -> None:
    paths.trades.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": pd.Timestamp("2024-01-02T14:30:00Z"),
                "target_entry_ts": pd.Timestamp("2024-01-02T14:31:00Z"),
                "target_exit_ts": pd.Timestamp("2024-01-02T14:33:00Z"),
                "position": 1,
                "execution_open": 100.0,
                "execution_close": 100.5,
                "gross_dollars": 25.0,
                "cost_dollars": 10.0,
                "net_dollars": 15.0,
            },
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0002",
                "timestamp": pd.Timestamp("2024-01-02T14:34:00Z"),
                "target_entry_ts": pd.Timestamp("2024-01-02T14:35:00Z"),
                "target_exit_ts": pd.Timestamp("2024-01-02T14:37:00Z"),
                "position": -1,
                "execution_open": 100.0,
                "execution_close": 101.0,
                "gross_dollars": -50.0,
                "cost_dollars": 10.0,
                "net_dollars": -60.0,
            },
        ]
    ).to_csv(paths.trades, index=False)
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=8, freq="min")
    rows = []
    for ts in timestamps:
        rows.append({"ts": ts, "market": "ES", "year": 2024, "open": 100.0, "high": 100.0, "low": 100.0})
    rows[1].update({"open": 100.0, "high": 102.0, "low": 99.0})
    rows[2].update({"open": 100.25, "high": 101.0, "low": 99.5})
    rows[3].update({"open": 100.5, "high": 100.5, "low": 100.5})
    rows[5].update({"open": 100.0, "high": 103.0, "low": 99.0})
    rows[6].update({"open": 100.5, "high": 102.0, "low": 99.5})
    rows[7].update({"open": 101.0, "high": 101.0, "low": 101.0})
    paths.bars.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(paths.bars, index=False)


def _complete_fixture(tmp_path: Path) -> AutopsyPaths:
    paths = _paths(tmp_path)
    _write_core_artifacts(paths)
    _write_trades_and_bars(paths)
    return paths


def test_clean_autopsy_report_generation(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)

    result = run_autopsy(
        hypothesis_id=HYPOTHESIS_ID,
        run=RUN_ID,
        paths=paths,
        market="ES",
    )

    codes = {item["code"] for item in result["classifications"]}
    assert {
        "TARGET_LOOKED_GOOD_BUT_POLICY_FAILED",
        "TARGET_POLICY_MISMATCH",
        "GROSS_EDGE_ABSENT",
        "COST_DRAG_DOMINANT",
        "OVERTRADING_OR_WEAK_FILTER",
        "PATH_OPPORTUNITY_NOT_CAPTURED",
        "FIRST_TOUCH_NO_GO",
        "FOLD_CONCENTRATION",
    }.issubset(codes)
    assert paths.json_out.exists()
    assert paths.md_out.exists()
    text = paths.md_out.read_text(encoding="utf-8")
    assert "## Evidence Timeline" in text
    assert "## What Looked Good" in text
    assert "## What Failed" in text
    assert "## Trader Lesson" in text
    assert "Fixed-Exit Versus Path Opportunity" in text
    assert "parameter selection" in text
    assert "tuning" not in text.lower()


def test_missing_wfa_manifest_fails_closed(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)
    paths.wfa_manifest.unlink()

    with pytest.raises(ValueError, match="missing required WFA prediction manifest"):
        run_autopsy(
            hypothesis_id=HYPOTHESIS_ID,
            run=RUN_ID,
            paths=paths,
            market="ES",
        )


def test_missing_trades_or_bars_produces_clear_blocker(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_core_artifacts(paths)

    result = run_autopsy(
        hypothesis_id=HYPOTHESIS_ID,
        run=RUN_ID,
        paths=paths,
        market="ES",
    )

    assert result["path_stats"] is None
    assert result["blocker_count"] == 1
    assert result["blockers"][0]["code"] == "MISSING_EVIDENCE"
    text = paths.md_out.read_text(encoding="utf-8")
    assert "Missing Evidence Blockers" in text
    assert "Path stats were not computed" in text


def test_stale_output_fails_closed_without_overwrite(tmp_path: Path) -> None:
    paths = _complete_fixture(tmp_path)
    paths.md_out.parent.mkdir(parents=True)
    paths.md_out.write_text("stale", encoding="utf-8")

    with pytest.raises(ValueError, match="stale output path exists"):
        run_autopsy(
            hypothesis_id=HYPOTHESIS_ID,
            run=RUN_ID,
            paths=paths,
            market="ES",
        )
