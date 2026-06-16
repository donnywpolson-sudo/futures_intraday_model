from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.audit_policy_run_level_overlap import (  # noqa: E402
    build_policy_run_level_overlap_audit,
    main,
)
from scripts.phase8_model_selection.evaluate_predictions import PolicyConfig  # noqa: E402


def _write_costs(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
markets:
  ES:
    point_value: 50.0
    tick_value: 10.0
    round_turn_cost_dollars: 10.0
    slippage_ticks_per_side: 0.25
""".strip(),
        encoding="utf-8",
    )
    return path


def _base_row(timestamp: pd.Timestamp, *, entry: float, exit_: float) -> dict[str, object]:
    return {
        "market": "ES",
        "year": 2024,
        "fold_id": "ES_research_0001",
        "timestamp": timestamp,
        "session_id": timestamp.strftime("%Y-%m-%d"),
        "session_segment_id": "rth",
        "split_group": "research",
        "prediction_type": "classification_probability",
        "calibration_id": "no_calibration",
        "model_config_hash": "model-hash",
        "feature_config_hash": "feature-hash",
        "execution_open": entry,
        "execution_close": exit_,
        "target_valid": True,
        "target_entry_ts": timestamp + pd.Timedelta(minutes=1),
        "target_exit_ts": timestamp + pd.Timedelta(minutes=16),
        "minutes_until_session_close": 60.0,
    }


def _add_policy_rows(rows: list[dict[str, object]], base: dict[str, object], item: dict[str, object]) -> None:
    rows.append(
        {
            **base,
            "model_id": "ridge_return_v1",
            "model_family": "ridge_regression",
            "target_name": "target_ret_15m",
            "prediction_type": "regression",
            "y_true": item["ret_true"],
            "y_pred_raw": item["ret_pred"],
            "y_pred_calibrated": item["ret_pred"],
            "p_long": None,
            "p_short": None,
            "p_flat": None,
            "p_fade_success": None,
            "p_trend_danger": None,
        }
    )
    rows.append(
        {
            **base,
            "model_id": "logistic_direction_v1",
            "model_family": "logistic_regression",
            "target_name": "target_sign_with_deadzone",
            "y_true": item["direction_true"],
            "y_pred_raw": item["p_long"] - item["p_short"],
            "y_pred_calibrated": item["p_long"] - item["p_short"],
            "p_long": item["p_long"],
            "p_short": item["p_short"],
            "p_flat": item["p_flat"],
            "p_fade_success": None,
            "p_trend_danger": None,
        }
    )
    rows.append(
        {
            **base,
            "model_id": "logistic_fade_success_v1",
            "model_family": "logistic_regression",
            "target_name": "target_fade_success_15m",
            "y_true": int(item["p_fade"] >= 0.5),
            "y_pred_raw": item["p_fade"],
            "y_pred_calibrated": item["p_fade"],
            "p_long": None,
            "p_short": None,
            "p_flat": None,
            "p_fade_success": item["p_fade"],
            "p_trend_danger": None,
        }
    )
    rows.append(
        {
            **base,
            "model_id": "logistic_trend_danger_v1",
            "model_family": "logistic_regression",
            "target_name": "target_trend_danger_30m",
            "y_true": int(item["p_trend"] >= 0.5),
            "y_pred_raw": item["p_trend"],
            "y_pred_calibrated": item["p_trend"],
            "p_long": None,
            "p_short": None,
            "p_flat": None,
            "p_fade_success": None,
            "p_trend_danger": item["p_trend"],
        }
    )


def _write_predictions(path: Path, *, include_target_times: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.date_range("2024-01-02T14:00:00Z", periods=3, freq="5min")
    items = [
        {
            "entry": 100.0,
            "exit": 101.0,
            "p_long": 0.80,
            "p_short": 0.10,
            "p_flat": 0.10,
            "p_fade": 0.80,
            "p_trend": 0.10,
            "direction_true": 1,
            "ret_true": 0.01,
            "ret_pred": 0.01,
        },
        {
            "entry": 101.0,
            "exit": 102.0,
            "p_long": 0.75,
            "p_short": 0.10,
            "p_flat": 0.15,
            "p_fade": 0.80,
            "p_trend": 0.10,
            "direction_true": 1,
            "ret_true": 0.01,
            "ret_pred": 0.01,
        },
        {
            "entry": 102.0,
            "exit": 101.0,
            "p_long": 0.10,
            "p_short": 0.80,
            "p_flat": 0.10,
            "p_fade": 0.80,
            "p_trend": 0.10,
            "direction_true": -1,
            "ret_true": -0.01,
            "ret_pred": -0.01,
        },
    ]
    rows: list[dict[str, object]] = []
    for timestamp, item in zip(timestamps, items):
        base = _base_row(timestamp, entry=item["entry"], exit_=item["exit"])
        if not include_target_times:
            base.pop("target_entry_ts")
            base.pop("target_exit_ts")
        _add_policy_rows(rows, base, item)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _policy() -> PolicyConfig:
    return PolicyConfig(
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
    )


def test_run_level_audit_reports_row_vs_run_cost_and_overlap(tmp_path: Path) -> None:
    predictions = _write_predictions(tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet")
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")
    json_out = tmp_path / "reports" / "phase8" / "run_level.json"
    md_out = tmp_path / "reports" / "phase8" / "run_level.md"

    report = build_policy_run_level_overlap_audit(
        predictions_path=predictions,
        costs_config=costs,
        json_out=json_out,
        md_out=md_out,
        run="fixture",
        policy=_policy(),
    )

    row_run = report["row_vs_run_level"]
    assert row_run["row_level"]["trade_count"] == 3
    assert row_run["run_count"] == 2
    assert row_run["one_bar_run_count"] == 1
    assert row_run["max_rows_per_run"] == 2
    assert row_run["gross_return_dollars"] == 150.0
    assert row_run["row_level_cost_dollars"] == 30.0
    assert row_run["run_level_estimated_cost_dollars"] == 20.0
    assert row_run["row_level_net_dollars"] == 120.0
    assert row_run["run_level_estimated_net_dollars"] == 130.0
    assert report["non_overlapping_target_windows"]["selected_trade_count"] == 1
    assert report["non_overlapping_target_windows"]["skipped_overlap_count"] == 2
    assert json.loads(json_out.read_text(encoding="utf-8"))["run"] == "fixture"
    assert "Run-level costs are a diagnostic sensitivity only" in md_out.read_text(encoding="utf-8")


def test_run_level_audit_fails_closed_without_target_windows(tmp_path: Path) -> None:
    predictions = _write_predictions(
        tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet",
        include_target_times=False,
    )
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="policy frame missing required diagnostic columns"):
        build_policy_run_level_overlap_audit(
            predictions_path=predictions,
            costs_config=costs,
            json_out=tmp_path / "reports" / "phase8" / "run_level.json",
            md_out=None,
            run="fixture",
            policy=_policy(),
        )


def test_run_level_audit_cli_writes_report(tmp_path: Path) -> None:
    predictions = _write_predictions(tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet")
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")
    json_out = tmp_path / "reports" / "phase8" / "run_level.json"
    md_out = tmp_path / "reports" / "phase8" / "run_level.md"

    result = main(
        [
            "--predictions",
            predictions.as_posix(),
            "--costs-config",
            costs.as_posix(),
            "--json-out",
            json_out.as_posix(),
            "--md-out",
            md_out.as_posix(),
            "--run",
            "fixture",
        ]
    )

    assert result == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["diagnostic_only"] is True
    assert payload["row_vs_run_level"]["run_count"] == 2
    assert md_out.exists()
