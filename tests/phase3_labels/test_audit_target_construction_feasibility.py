from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase3_labels.audit_target_construction_feasibility import (  # noqa: E402
    build_target_feasibility_report,
    main,
)


def _write_costs(path: Path, *, include_market: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            """
markets:
  ES:
    tick_size: 0.25
    tick_value: 12.5
    point_value: 50.0
    min_profit_ticks: 2.0
    min_stop_ticks: 4.0
    round_turn_cost_ticks: 2.0
    round_turn_cost_dollars: 25.0
    provisional: false
""".strip()
            if include_market
            else "markets: {}\n"
        ),
        encoding="utf-8",
    )
    return path


def _rows(row_count: int = 36) -> list[dict[str, object]]:
    start = pd.Timestamp("2024-01-02T14:30:00Z")
    rows: list[dict[str, object]] = []
    for index in range(row_count):
        ts = start + pd.Timedelta(minutes=index)
        valid_target = index + 16 < row_count
        open_price = 100.0
        high = 100.25
        low = 99.75
        close = 100.0
        rows.append(
            {
                "ts": ts,
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100,
                "causal_valid": True,
                "session_segment_id": "ES_2024_session",
                "is_synthetic": False,
                "valid_ohlcv": True,
                "boundary_session_flag": False,
                "roll_window_flag": False,
                "target_valid": valid_target,
                "target_entry_ts": (start + pd.Timedelta(minutes=index + 1))
                if valid_target
                else pd.NaT,
                "target_exit_ts": (start + pd.Timedelta(minutes=index + 16))
                if valid_target
                else pd.NaT,
                "target_gross_dollars_15m": 50.0 if index == 0 else (-50.0 if index == 16 else 0.0),
                "target_estimated_cost_dollars": 25.0 if valid_target else float("nan"),
                "target_sign_with_deadzone": 1 if index == 0 else (-1 if index == 16 else 0),
            }
        )

    rows[2]["high"] = 101.0
    rows[18]["low"] = 99.0
    return rows


def _write_input(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _write_split_plan(path: Path, *, overlap: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    folds = [
        {
            "market": "ES",
            "fold_id": "ES_research_0001",
            "split_group": "research",
            "test_start": "2024-01-02T14:30:00+00:00",
            "test_end": "2024-01-02T14:45:00+00:00",
            "selection_allowed": True,
        },
        {
            "market": "ES",
            "fold_id": "ES_research_0002",
            "split_group": "research",
            "test_start": "2024-01-02T14:40:00+00:00" if overlap else "2024-01-02T14:46:00+00:00",
            "test_end": "2024-01-02T15:05:00+00:00",
            "selection_allowed": True,
        },
    ]
    path.write_text(json.dumps({"folds": folds}), encoding="utf-8")
    return path


def test_target_feasibility_groups_non_overlapping_events_and_barrier_labels(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")

    report = build_target_feasibility_report(input_paths=[input_path], costs_config=costs_path)

    assert report["source_row_count"] == 36
    assert report["non_overlapping_event_count"] == 2
    assert report["skipped_overlapping_valid_rows"] == 18

    candidates = {item["candidate"]: item for item in report["candidates"]}
    fixed = candidates["current_fixed_15m_deadzone_direction_oracle"]
    assert fixed["selected_event_count"] == 2
    assert fixed["long_label_count"] == 1
    assert fixed["short_label_count"] == 1
    assert fixed["net_oracle_dollars"] == 50.0
    assert fixed["breakdown_available"] == {
        "market_year": True,
        "side": True,
        "fold": True,
        "regime_period": True,
    }
    assert fixed["by_market_year"][0]["market"] == "ES"
    assert fixed["by_market_year"][0]["year"] == 2024
    assert fixed["by_regime_period"][0]["regime_period"] == "calendar_2024_2024"
    assert fixed["by_regime_period"][0]["selected_event_count"] == 2
    assert fixed["by_fold"][0]["fold_id"] == "ES_research_0001"
    side_rows = {row["side"]: row for row in fixed["by_side"]}
    assert side_rows["long"]["selected_event_count"] == 1
    assert side_rows["short"]["selected_event_count"] == 1

    barrier = candidates["pathwise_first_hit_barrier_15m_directional"]
    assert barrier["selected_event_count"] == 2
    assert barrier["long_label_count"] == 1
    assert barrier["short_label_count"] == 1
    assert barrier["ambiguous_event_count"] == 0
    assert barrier["by_market_year"][0]["selected_event_count"] == 2


def test_target_feasibility_maps_events_to_split_plan_folds(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    split_plan = _write_split_plan(tmp_path / "reports" / "split_plan.json")

    report = build_target_feasibility_report(
        input_paths=[input_path],
        costs_config=costs_path,
        split_plan_json=split_plan,
    )

    assert report["fold_mapping"]["fold_mapping_enabled"] is True
    assert report["fold_mapping"]["selection_allowed_research_folds_mapped"] == 2
    candidates = {item["candidate"]: item for item in report["candidates"]}
    by_fold = candidates["pathwise_first_hit_barrier_15m_directional"]["by_fold"]
    assert [(row["fold_id"], row["selected_event_count"]) for row in by_fold] == [
        ("ES_research_0001", 1),
        ("ES_research_0002", 1),
    ]


def test_target_feasibility_accepts_explicit_regime_periods(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")

    report = build_target_feasibility_report(
        input_paths=[input_path],
        costs_config=costs_path,
        regime_periods=[("recent", 2024, 2024)],
    )

    assert report["regime_periods"] == [
        {"name": "recent", "start_year": 2024, "end_year": 2024}
    ]
    candidates = {item["candidate"]: item for item in report["candidates"]}
    assert candidates["pathwise_first_hit_barrier_15m_directional"]["by_regime_period"][0][
        "regime_period"
    ] == "recent"


def test_target_feasibility_rejects_overlapping_regime_periods(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="regime periods must not overlap"):
        build_target_feasibility_report(
            input_paths=[input_path],
            costs_config=costs_path,
            regime_periods=[("a", 2020, 2024), ("b", 2024, 2026)],
        )


def test_target_feasibility_fails_closed_on_overlapping_split_plan_folds(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    split_plan = _write_split_plan(tmp_path / "reports" / "split_plan.json", overlap=True)

    with pytest.raises(SystemExit, match="overlapping test folds"):
        build_target_feasibility_report(
            input_paths=[input_path],
            costs_config=costs_path,
            split_plan_json=split_plan,
        )


def test_target_feasibility_fails_closed_on_missing_required_columns(tmp_path: Path) -> None:
    rows = _rows()
    for row in rows:
        row.pop("target_exit_ts")
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", rows)
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="missing required columns"):
        build_target_feasibility_report(input_paths=[input_path], costs_config=costs_path)


def test_target_feasibility_fails_closed_on_missing_explicit_costs(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml", include_market=False)

    with pytest.raises(SystemExit, match="cost assumptions must be explicit"):
        build_target_feasibility_report(input_paths=[input_path], costs_config=costs_path)


def test_target_feasibility_fails_closed_on_duplicate_keys(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["ts"] = rows[0]["ts"]
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", rows)
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")

    with pytest.raises(SystemExit, match="duplicate market/year/ts"):
        build_target_feasibility_report(input_paths=[input_path], costs_config=costs_path)


def test_target_feasibility_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path / "data" / "labeled" / "ES" / "2024.parquet", _rows())
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    json_out = tmp_path / "reports" / "target_feasibility.json"
    md_out = tmp_path / "reports" / "target_feasibility.md"

    exit_code = main(
        [
            "--input-parquet",
            str(input_path),
            "--costs-config",
            str(costs_path),
            "--split-plan-json",
            str(_write_split_plan(tmp_path / "reports" / "split_plan.json")),
            "--regime-period",
            "recent:2024-2024",
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    assert exit_code == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["diagnostic_only"] is True
    assert payload["regime_periods"][0]["name"] == "recent"
    assert payload["decision"]["phase3_changed"] is False
    assert md_out.exists()
