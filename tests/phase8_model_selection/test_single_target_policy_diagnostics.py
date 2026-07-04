from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.single_target_policy_diagnostics import (  # noqa: E402
    build_arg_parser,
    evaluate_single_target_policy_diagnostics,
    main,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_models(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
models:
  logistic_opening_range_acceptance_continuation_30m_v1:
    family: logistic_regression
    task: classification
    enabled: true
    target: target_sign_with_deadzone
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_costs(path: Path, *, include_es: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if include_es:
        payload = """
cost_model:
  name: fixture_costs
  live_fill_model_available: false
markets:
  ES:
    point_value: 50.0
    tick_value: 12.5
    slippage_ticks_per_side: 0.0
    round_turn_cost_dollars: 10.0
""".rstrip()
    else:
        payload = """
cost_model:
  name: fixture_costs
  live_fill_model_available: false
markets: {}
""".strip()
    path.write_text(
        payload,
        encoding="utf-8",
    )
    return path


def _base_rows() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02T14:30:00Z", periods=6, freq="15min")
    values = [
        (0.70, 0.20, 0.10, 1),
        (0.20, 0.70, 0.10, -1),
        (0.35, 0.20, 0.45, 0),
        (0.65, 0.25, 0.10, 1),
        (0.25, 0.60, 0.15, -1),
        (0.30, 0.25, 0.45, 0),
    ]
    rows: list[dict[str, object]] = []
    for idx, (p_long, p_short, p_flat, y_true) in enumerate(values):
        timestamp = timestamps[idx]
        rows.append(
            {
                "market": "ES",
                "year": 2024,
                "fold_id": "ES_research_0001",
                "timestamp": timestamp,
                "session_id": "2024-01-02",
                "session_segment_id": "rth",
                "split_group": "research",
                "model_id": "logistic_opening_range_acceptance_continuation_30m_v1",
                "model_family": "logistic_regression",
                "target_name": "target_sign_with_deadzone",
                "prediction_type": "classification_probability",
                "y_true": y_true,
                "y_pred_raw": p_long - p_short,
                "y_pred_calibrated": p_long - p_short,
                "p_long": p_long,
                "p_short": p_short,
                "p_flat": p_flat,
                "p_fade_success": None,
                "p_trend_adverse_long_30m": None,
                "p_trend_favorable_long_30m": None,
                "p_trend_adverse_short_30m": None,
                "p_trend_favorable_short_30m": None,
                "p_trend_danger": None,
                "calibration_id": "no_calibration",
                "model_config_hash": "model-hash",
                "feature_config_hash": "feature-hash",
                "execution_open": 100.0 + idx,
                "execution_close": 101.0 + idx,
                "target_valid": True,
                "target_entry_ts": timestamp + pd.Timedelta(minutes=1),
                "target_exit_ts": timestamp + pd.Timedelta(minutes=31),
                "minutes_until_session_close": 120.0,
            }
        )
    return pd.DataFrame(rows)


def _write_predictions(
    path: Path,
    *,
    mutate: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> Path:
    frame = _base_rows()
    if mutate is not None:
        frame = mutate(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def _write_split_plan(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "profile": "tier_1",
                "resolved_profile": "tier_1_research",
                "config_hash": "split-config-hash",
                "markets": ["ES"],
                "years": [2024],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_manifest(path: Path, prediction_path: Path, *, run: str = "single_target_policy_run") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    split_plan = _write_split_plan(path.parent / "split_plan.json")
    payload: dict[str, object] = {
        "failure_count": 0,
        "run": run,
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2024],
        "prediction_markets": ["ES"],
        "prediction_years": [2024],
        "prediction_path": prediction_path.as_posix(),
        "prediction_count": int(len(pd.read_parquet(prediction_path))),
        "output_file_hashes": {prediction_path.as_posix(): _sha256(prediction_path)},
        "input_file_hashes": {split_plan.as_posix(): _sha256(split_plan)},
        "split_plan_path": split_plan.as_posix(),
        "split_plan_hash": _sha256(split_plan),
        "split_plan_profile": "tier_1",
        "split_plan_resolved_profile": "tier_1_research",
        "split_plan_config_hash": "split-config-hash",
        "stale_output_path_exists": False,
        "artifact_evidence_ready": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_adapter(
    tmp_path: Path,
    *,
    prediction_mutator: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    include_es_costs: bool = True,
) -> dict[str, object]:
    prediction_path = _write_predictions(
        tmp_path / "predictions" / "oos_predictions.parquet",
        mutate=prediction_mutator,
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "predictions_manifest.json",
        prediction_path,
    )
    return evaluate_single_target_policy_diagnostics(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=_write_costs(tmp_path / "configs" / "costs.yaml", include_es=include_es_costs),
        models_config=_write_models(tmp_path / "configs" / "models.yaml"),
        reports_root=tmp_path / "reports" / "single_target_policy",
        run="single_target_policy_run",
    )


def test_cli_requires_explicit_inputs() -> None:
    parser = build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_single_target_policy_diagnostics_writes_costed_pnl_reports(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path)

    assert result["failure_count"] == 0
    assert result["diagnostic_only"] is True
    assert result["promotion_allowed"] is False
    assert result["model_promotion_allowed"] is False
    assert result["live_execution_ready"] is False
    assert result["policy_contract"] == "single_target_unique_max_probability_non_overlapping_one_contract"
    assert result["fixed_exit_policy_mismatch"] is True
    assert result["decisive_economic_evidence_allowed"] is False
    assert result["economic_approval_allowed"] is False
    assert result["economic_rejection_allowed"] is False
    assert result["target_policy_compatibility"]["compatible"] is False
    assert result["target_policy_compatibility"]["policy_evaluation_basis"] == "fixed_horizon_exit"
    assert result["target_policy_contract"]["payoff_basis"] == "path_favorable_excursion"
    assert result["trade_count"] == 2
    assert result["candidate_trade_count"] == 4
    assert result["blocked_by_execution_overlap"] == 2
    assert result["gross_return_dollars"] == pytest.approx(100.0)
    assert result["cost_dollars"] == pytest.approx(20.0)
    assert result["net_return_dollars"] == pytest.approx(80.0)

    diagnostics_path = result["diagnostics_path"]
    summary_path = result["policy_summary_output_path"]
    turnover_path = result["turnover_output_path"]
    trades_path = result["trades_output_path"]
    assert diagnostics_path.exists()
    assert summary_path.exists()
    assert turnover_path.exists()
    assert trades_path.exists()

    saved = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    summaries = pd.read_csv(summary_path)
    trades = pd.read_csv(trades_path)
    assert saved["failure_count"] == 0
    assert saved["decisive_economic_evidence_allowed"] is False
    assert saved["economic_rejection_allowed"] is False
    assert summaries.loc[summaries["scope"].eq("overall"), "net_return_dollars"].iloc[0] == pytest.approx(80.0)
    assert trades["position"].tolist() == [1, 1]
    assert trades["net_dollars"].sum() == pytest.approx(80.0)


def test_single_target_policy_tie_is_flat_not_tuned_trade(tmp_path: Path) -> None:
    result = _run_adapter(
        tmp_path,
        prediction_mutator=lambda frame: frame.assign(
            p_long=[0.45, *frame["p_long"].iloc[1:].tolist()],
            p_short=[0.45, *frame["p_short"].iloc[1:].tolist()],
            p_flat=[0.10, *frame["p_flat"].iloc[1:].tolist()],
        ),
    )

    assert result["failure_count"] == 0
    assert result["candidate_trade_count"] == 3
    assert result["trade_count"] == 2
    assert result["policy_metrics"]["overall"]["no_direction_signal"] == 3


def test_single_target_policy_missing_costs_fails_closed(tmp_path: Path) -> None:
    result = _run_adapter(tmp_path, include_es_costs=False)

    assert result["failure_count"] > 0
    assert any("missing usable costs for markets" in item for item in result["failures"])
    assert result["promotion_allowed"] is False


def test_single_target_policy_missing_target_window_fails_closed(tmp_path: Path) -> None:
    result = _run_adapter(
        tmp_path,
        prediction_mutator=lambda frame: frame.assign(target_exit_ts=pd.NaT),
    )

    assert result["failure_count"] > 0
    assert any("missing target_entry_ts/target_exit_ts" in item for item in result["failures"])
    assert result["model_promotion_allowed"] is False


def test_main_returns_nonzero_on_policy_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prediction_path = _write_predictions(tmp_path / "predictions" / "oos_predictions.parquet")
    manifest_path = _write_manifest(tmp_path / "reports" / "wfa" / "predictions_manifest.json", prediction_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "single_target_policy_diagnostics.py",
            "--predictions",
            prediction_path.as_posix(),
            "--predictions-manifest",
            manifest_path.as_posix(),
            "--costs-config",
            _write_costs(tmp_path / "configs" / "costs.yaml", include_es=False).as_posix(),
            "--models-config",
            _write_models(tmp_path / "configs" / "models.yaml").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "single_target_policy").as_posix(),
            "--run",
            "single_target_policy_run",
        ],
    )

    assert main() == 1
