from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.audit_event_level_edge_feasibility import (  # noqa: E402
    build_arg_parser,
    build_event_level_edge_feasibility,
    main,
)
from scripts.phase8_model_selection.evaluate_predictions import PolicyConfig  # noqa: E402
from tests.phase8_model_selection.side_aware_fixture import add_side_aware_trend_rows  # noqa: E402


def _write_costs(path: Path, *, include_market: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            """
markets:
  ES:
    point_value: 50.0
    tick_value: 10.0
    round_turn_cost_dollars: 10.0
    slippage_ticks_per_side: 0.25
""".strip()
            if include_market
            else "markets: {}\n"
        ),
        encoding="utf-8",
    )
    return path


def _base_row(
    timestamp: pd.Timestamp,
    *,
    entry: float,
    exit_: float,
    session_id: str = "2024-01-02",
    include_target_times: bool = True,
) -> dict[str, object]:
    row: dict[str, object] = {
        "market": "ES",
        "year": 2024,
        "fold_id": "ES_research_0001",
        "timestamp": timestamp,
        "session_id": session_id,
        "session_segment_id": "rth",
        "split_group": "research",
        "prediction_type": "classification_probability",
        "calibration_id": "no_calibration",
        "model_config_hash": "model-hash",
        "feature_config_hash": "feature-hash",
        "execution_open": entry,
        "execution_close": exit_,
        "target_valid": True,
        "minutes_until_session_close": 60.0,
    }
    if include_target_times:
        row["target_entry_ts"] = timestamp + pd.Timedelta(minutes=1)
        row["target_exit_ts"] = timestamp + pd.Timedelta(minutes=16)
    return row


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
    add_side_aware_trend_rows(rows, base, item)


def _write_predictions(
    path: Path,
    *,
    include_target_times: bool = True,
    duplicate_policy_key: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.to_datetime(
        [
            "2024-01-02T14:00:00Z",
            "2024-01-02T14:05:00Z",
            "2024-01-02T14:20:00Z",
            "2024-01-02T14:40:00Z",
        ]
    )
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
        {
            "entry": 101.0,
            "exit": 100.0,
            "p_long": 0.70,
            "p_short": 0.20,
            "p_flat": 0.10,
            "p_fade": 0.80,
            "p_trend": 0.10,
            "direction_true": -1,
            "ret_true": -0.01,
            "ret_pred": 0.01,
        },
    ]
    rows: list[dict[str, object]] = []
    for timestamp, item in zip(timestamps, items):
        base = _base_row(
            timestamp,
            entry=item["entry"],
            exit_=item["exit"],
            include_target_times=include_target_times,
        )
        _add_policy_rows(rows, base, item)
    if duplicate_policy_key:
        duplicate_base = _base_row(
            timestamps[0],
            entry=100.0,
            exit_=101.0,
            session_id="duplicate-session",
            include_target_times=include_target_times,
        )
        _add_policy_rows(rows, duplicate_base, items[0])
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _policy() -> PolicyConfig:
    return PolicyConfig(
        long_short_margin=0.05,
        min_fade_success=0.50,
        max_trend_danger=0.50,
    )


def test_event_level_audit_cli_predictions_has_no_implicit_default() -> None:
    args = build_arg_parser().parse_args(["--json-out", "reports/phase8/events.json"])

    assert args.predictions is None


def test_event_level_audit_cli_missing_predictions_fails_clearly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--json-out", (tmp_path / "reports" / "phase8" / "events.json").as_posix()])

    assert exc_info.value.code == 2
    assert "--predictions is required" in capsys.readouterr().err


def test_event_level_audit_cli_accepts_explicit_report_scoped_predictions(tmp_path: Path) -> None:
    prediction_path = tmp_path / "reports" / "wfa" / "fixture_predictions.parquet"

    args = build_arg_parser().parse_args(
        [
            "--predictions",
            prediction_path.as_posix(),
            "--json-out",
            (tmp_path / "reports" / "phase8" / "events.json").as_posix(),
        ]
    )

    assert Path(args.predictions).as_posix() == prediction_path.as_posix()


def test_event_level_audit_selects_non_overlapping_events(tmp_path: Path) -> None:
    predictions = _write_predictions(tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet")
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")
    json_out = tmp_path / "reports" / "phase8" / "events.json"
    md_out = tmp_path / "reports" / "phase8" / "events.md"

    report = build_event_level_edge_feasibility(
        predictions_path=predictions,
        costs_config=costs,
        json_out=json_out,
        md_out=md_out,
        run="fixture",
        policy=_policy(),
    )

    assert report["source_prediction_rows"] == 32
    assert report["current_policy_traded_rows"] == 3
    assert report["direction_candidate_rows"] == 4
    assert report["non_overlapping_event_count"] == 3
    assert report["skipped_overlapping_rows"] == 1
    overall = report["event_metrics"]["overall"]
    assert overall["event_count"] == 3
    assert overall["long_count"] == 2
    assert overall["short_count"] == 1
    assert overall["gross_return_dollars"] == 50.0
    assert overall["cost_dollars"] == 30.0
    assert overall["net_return_dollars"] == 20.0
    assert overall["direction_accuracy"] == pytest.approx(2 / 3)
    assert report["event_metrics"]["by_rank_bucket"]
    assert report["decision"]["decision"] == "does_not_support_new_edge_model_research"
    assert json.loads(json_out.read_text(encoding="utf-8"))["run"] == "fixture"
    assert "non-overlapping target-window events" in md_out.read_text(encoding="utf-8")


def test_event_level_audit_fails_closed_without_target_windows(tmp_path: Path) -> None:
    predictions = _write_predictions(
        tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet",
        include_target_times=False,
    )
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="policy executable signals missing target_entry_ts/target_exit_ts"):
        build_event_level_edge_feasibility(
            predictions_path=predictions,
            costs_config=costs,
            json_out=tmp_path / "reports" / "phase8" / "events.json",
            md_out=None,
            run="fixture",
            policy=_policy(),
        )


def test_event_level_audit_fails_closed_on_duplicate_policy_keys(tmp_path: Path) -> None:
    predictions = _write_predictions(
        tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet",
        duplicate_policy_key=True,
    )
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="duplicate policy keys"):
        build_event_level_edge_feasibility(
            predictions_path=predictions,
            costs_config=costs,
            json_out=tmp_path / "reports" / "phase8" / "events.json",
            md_out=None,
            run="fixture",
            policy=_policy(),
        )


def test_event_level_audit_fails_closed_on_missing_costs(tmp_path: Path) -> None:
    predictions = _write_predictions(tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet")
    costs = _write_costs(tmp_path / "configs" / "costs.yaml", include_market=False)

    with pytest.raises(SystemExit, match="missing usable costs"):
        build_event_level_edge_feasibility(
            predictions_path=predictions,
            costs_config=costs,
            json_out=tmp_path / "reports" / "phase8" / "events.json",
            md_out=None,
            run="fixture",
            policy=_policy(),
        )


def test_event_level_audit_cli_writes_report(tmp_path: Path) -> None:
    predictions = _write_predictions(tmp_path / "data" / "predictions" / "run" / "oos_predictions.parquet")
    costs = _write_costs(tmp_path / "configs" / "costs.yaml")
    json_out = tmp_path / "reports" / "phase8" / "events.json"

    result = main(
        [
            "--predictions",
            predictions.as_posix(),
            "--costs-config",
            costs.as_posix(),
            "--json-out",
            json_out.as_posix(),
            "--run",
            "fixture",
        ]
    )

    assert result == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["diagnostic_only"] is True
    assert payload["non_overlapping_event_count"] == 3
