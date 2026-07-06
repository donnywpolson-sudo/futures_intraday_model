from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from scripts.validation import run_opening_range_acceptance_wfa_materialization as adapter
from tests.phase9_research.test_es_30m_target_smoke_harness import (
    _cost_config,
    _opening_range_frame,
)


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "policy": {
                    "random_splits_allowed": False,
                    "final_holdout_tuning_allowed": False,
                    "hyperparameter_tuning_allowed_initially": False,
                },
                "models": {
                    adapter.MODEL_ID: {
                        "stage": "phase_7a_linear_controls",
                        "family": "logistic_regression",
                        "task": "classification",
                        "enabled": True,
                        "requires_optional_dependency": False,
                        "target": adapter.MODEL_TARGET,
                    }
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "hypotheses": [
                    {
                        "target_hypothesis_id": adapter.HYPOTHESIS_ID,
                        "status": "FROZEN",
                        "wfa_allowed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_statuses(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "hypothesis_id": adapter.HYPOTHESIS_ID,
                "stage": "phase9_locked_smoke",
                "status": "FROZEN",
                "evidence": [],
                "trial_id": "frozen",
                "notes": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_costs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "markets": {
                    "ES": {
                        "tick_size": 0.25,
                        "tick_value": 12.5,
                        "round_turn_cost_dollars": 25.0,
                        "min_profit_ticks": 2.0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _write_inputs(root: Path) -> None:
    (root / "ES").mkdir(parents=True, exist_ok=True)
    for year in (2023, 2024):
        frame = _opening_range_frame().copy()
        frame["year"] = year
        frame["session_segment_id"] = f"ES_{year}_01_02"
        frame.to_parquet(root / "ES" / f"{year}.parquet", index=False)
    (root / "feature_cols.json").write_text(json.dumps(["feature_signal"], indent=2), encoding="utf-8")


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "input_root": tmp_path / "data" / "feature_matrices",
        "output_root": tmp_path
        / "data"
        / "feature_matrices"
        / "opening_range_acceptance_continuation_30m_v1_wfa_smoke",
        "reports_root": tmp_path / "reports" / "pipeline_audit",
        "costs_config": tmp_path / "configs" / "costs.yaml",
        "models_config": tmp_path / "configs" / "models_opening_range_acceptance_continuation_30m_v1.yaml",
        "registry": tmp_path / "manifests" / "target_hypotheses" / "registry.json",
        "trial_statuses": tmp_path / "manifests" / "target_hypotheses" / "trial_statuses.jsonl",
    }


def _setup(tmp_path: Path) -> dict[str, Path]:
    paths = _paths(tmp_path)
    _write_inputs(paths["input_root"])
    _write_costs(paths["costs_config"])
    _write_config(paths["models_config"])
    _write_registry(paths["registry"])
    _write_statuses(paths["trial_statuses"])
    return paths


def _expected(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return adapter.expected_generated_paths(
        output_root=paths["output_root"],
        reports_root=paths["reports_root"],
        markets=("ES",),
        years=(2023, 2024),
        repo_root=tmp_path,
    )


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    paths = _setup(tmp_path)
    return adapter.build_report(
        repo_root=tmp_path,
        **paths,
        staged_generated_paths=[],
        ignored_generated_paths=_expected(paths, tmp_path),
        generated_at_utc="2026-07-04T00:00:00Z",
        **kwargs,
    )


def test_materialize_frame_maps_frozen_target_to_wfa_contract() -> None:
    frame = _opening_range_frame()
    materialized = adapter.materialize_wfa_frame(
        frame,
        cost_config=_cost_config(),
        feature_cols=["feature_signal"],
    )

    assert materialized.loc[29, "target_valid"] == False
    assert pd.isna(materialized.loc[29, "target_entry_price"])
    assert materialized.loc[30, "target_valid"] == True
    assert materialized.loc[30, "target_sign_with_deadzone"] == 1
    assert materialized.loc[30, "target_entry_price"] == frame.loc[31, "open"]
    assert materialized.loc[30, "target_exit_price"] == frame.loc[60, "open"]
    assert materialized.loc[30, "training_row_valid"] == True
    assert materialized.loc[110, "target_sign_with_deadzone"] == 0


def test_materialize_frame_rejects_target_features() -> None:
    try:
        adapter.materialize_wfa_frame(
            _opening_range_frame(),
            cost_config=_cost_config(),
            feature_cols=["target_sign_with_deadzone"],
        )
    except ValueError as exc:
        assert "target-derived columns" in str(exc)
    else:
        raise AssertionError("expected target feature rejection")


def test_model_config_is_fixed_single_logistic_target() -> None:
    assert adapter.validate_model_config(Path("configs/models_opening_range_acceptance_continuation_30m_v1.yaml")) == []


def test_dry_run_ready_without_execution(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == adapter.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 5
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["wfa_model_training_approved"] is False


def test_execute_requires_exact_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token="wrong")

    assert report["summary"]["status"] == adapter.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "execution_approval_token_present_when_execute"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_stale_output_fails_closed(tmp_path: Path) -> None:
    paths = _setup(tmp_path)
    stale = paths["output_root"] / "ES" / "2023.parquet"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"stale")

    report = adapter.build_report(
        repo_root=tmp_path,
        **paths,
        staged_generated_paths=[],
        ignored_generated_paths=_expected(paths, tmp_path),
        generated_at_utc="2026-07-04T00:00:00Z",
    )

    assert report["summary"]["status"] == adapter.STATUS_NO_GO
    assert any(
        check["name"] == "output_paths_absent_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_approved_execute_writes_materialized_outputs_in_temp_root(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token=adapter.APPROVAL_TOKEN)

    paths = _paths(tmp_path)
    assert report["summary"]["status"] == adapter.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["generated_output_count"] == 5
    assert (paths["output_root"] / "ES" / "2023.parquet").exists()
    assert (paths["output_root"] / "feature_cols.json").exists()
    assert (paths["reports_root"] / f"{adapter.REPORT_STEM}.json").exists()
    out = pd.read_parquet(paths["output_root"] / "ES" / "2023.parquet")
    assert "target_direction_opening_range_acceptance_continuation_30m" in out.columns
    assert out.loc[30, "target_sign_with_deadzone"] == 1
