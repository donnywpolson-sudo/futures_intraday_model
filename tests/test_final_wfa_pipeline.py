import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

import pipeline.common.config as config_module
from pipeline.common.config import DataSectionConfig, RootConfig
from pipeline.features.frozen import create_frozen_feature_set
from pipeline.final_wfa import run_final_wfa_pipeline
from pipeline.modeling.full_research import _feature_set_id
from pipeline.orchestration.stage_plan import START_STAGE_NUM, build_stage_plan, normalize_start_stage
from pipeline.validation.final_lineage import file_sha256
from pipeline.validation.final_experiment_diagnostics import (
    FINAL_PROFILE_COMPARISON_JSON,
    build_final_threshold_used_row,
    update_final_threshold_profile_comparison,
)


def _cfg(root: Path) -> RootConfig:
    cfg = RootConfig(
        symbols=["ES"],
        start_year=2025,
        end_year=2025,
        data=DataSectionConfig(root=str(root)),
    )
    cfg.walkforward.wf_train_days = 30
    cfg.walkforward.wf_test_days = 20
    cfg.walkforward.wf_step_days = 20
    cfg.target.target_15m_horizon = 1
    return cfg


def _write_expanded(root: Path) -> None:
    start = datetime(2025, 1, 1)
    n = 80
    df = pl.DataFrame(
        {
            "ts_event": [start + timedelta(days=i) for i in range(n)],
            "open": [100.0 + i * 0.1 for i in range(n)],
            "high": [101.0 + i * 0.1 for i in range(n)],
            "low": [99.0 + i * 0.1 for i in range(n)],
            "close": [100.5 + i * 0.1 for i in range(n)],
            "volume": [1000 + i for i in range(n)],
            "target_15m_ret": [float((i % 5) - 2) for i in range(n)],
            "ret_lag_1": [float((i % 3) - 1) for i in range(n)],
            "roll_vol_5": [float(i % 7) for i in range(n)],
            "roll_volume_5": [float(100 + (i % 11)) for i in range(n)],
            "roll_range_1": [float((i % 4) + 1) for i in range(n)],
        }
    )
    out = root / "ES" / "2025.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)


def _write_frozen(tmp_path: Path, cfg: RootConfig, expanded_root: Path) -> Path:
    reports = tmp_path / "reports/validation"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "stage_22_train_only_selection_audit_report.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    frozen = tmp_path / "data/frozen_features/phase5_v1"
    create_frozen_feature_set(
        config=cfg,
        run_id="run_test",
        profile="tier_1_bare_minimum_alpha",
        source_feature_matrix_root=expanded_root,
        output_root=frozen,
    )
    features = ["ret_lag_1", "roll_vol_5", "roll_volume_5", "roll_range_1"]
    (frozen / "feature_cols.json").write_text(json.dumps({"feature_cols": features}), encoding="utf-8")
    manifest = json.loads((frozen / "manifest.json").read_text(encoding="utf-8"))
    manifest["selected_feature_count"] = len(features)
    manifest["train_only"] = True
    manifest["leakage_check"] = "PASS"
    (frozen / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return frozen


def test_final_wfa_stage_resolution():
    cfg = RootConfig()

    assert normalize_start_stage("final_wfa") == "final_wfa"
    assert START_STAGE_NUM["final_wfa"] == 24
    assert build_stage_plan("final_wfa", cfg)[23]["status"] == "PENDING"


def test_final_wfa_refuses_missing_stage23(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expanded = tmp_path / "data/feature_matrices/expanded"
    _write_expanded(expanded)

    with pytest.raises(RuntimeError, match="Stage 23 frozen feature set MISSING"):
        run_final_wfa_pipeline(
            config=_cfg(expanded),
            run_id="run_test",
            profile="tier_1_bare_minimum_alpha",
            frozen_root=tmp_path / "missing_frozen",
            feature_matrix_root=expanded,
        )


def test_final_wfa_generates_full_coverage_and_lineage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expanded = tmp_path / "data/feature_matrices/expanded"
    _write_expanded(expanded)
    cfg = _cfg(expanded)
    frozen = _write_frozen(tmp_path, cfg, expanded)

    result = run_final_wfa_pipeline(
        config=cfg,
        run_id="run_test",
        profile="tier_1_bare_minimum_alpha",
        frozen_root=frozen,
        feature_matrix_root=expanded,
    )

    stage24 = pl.read_parquet(result["stage24_path"])
    stage25 = pl.read_parquet(result["stage25_path"])
    features = json.loads((frozen / "feature_cols.json").read_text(encoding="utf-8"))["feature_cols"]
    stage26 = json.loads(Path(result["stage26_path"]).read_text(encoding="utf-8"))
    stage27 = json.loads(Path(result["stage27_path"]).read_text(encoding="utf-8"))
    threshold_used = json.loads(Path("reports/validation/final_threshold_used.json").read_text(encoding="utf-8"))
    experiment = json.loads(Path("reports/validation/final_experiment_comparison.json").read_text(encoding="utf-8"))[0]

    assert set(stage25.select("symbol").unique()["symbol"]) == {"ES"}
    assert stage25.select(["symbol", "split"]).unique().height == result["expected_split_slots"]
    assert stage25["prediction"].null_count() == 0
    assert len(threshold_used) == result["expected_split_slots"]
    assert {r["run_id"] for r in threshold_used} == {"run_test"}
    assert experiment["expected_rows"] == result["expected_split_slots"]
    assert Path("reports/validation/final_threshold_outliers.json").exists()
    assert set(stage24["feature_set_id"].unique().to_list()) == {_feature_set_id(features)}
    assert not Path("artifacts/selectors").exists()
    assert stage26["source_artifact_checksum"] == file_sha256(result["stage25_path"])
    assert stage27["source_artifact_checksum"] == file_sha256(result["stage26_path"])


def test_final_p995_p999_profiles_exist_and_production_unchanged(monkeypatch):
    monkeypatch.setenv("CONFIG_ENV", "tier_1_final_threshold_p999_experiment")
    config_module._LOADED = False
    p999 = config_module.load_config("tier_1_final_threshold_p999_experiment")
    assert p999.execution.threshold_mode == "prediction_abs_quantile"
    assert p999.execution.threshold_quantile == 0.999
    assert p999.symbols == ["ES", "CL", "ZN"]

    config_module._LOADED = False
    p995 = config_module.load_config("tier_1_final_threshold_p995_experiment")
    assert p995.execution.threshold_mode == "prediction_abs_quantile"
    assert p995.execution.threshold_quantile == 0.995
    assert p995.symbols == ["ES", "CL", "ZN"]

    config_module._LOADED = False
    prod = config_module.load_config("tier_1_bare_minimum_alpha")
    assert prod.execution.threshold_mode == "fixed"
    assert prod.execution.prediction_entry_threshold == 0.25


def test_final_threshold_calibration_rejects_non_train_source():
    cfg = RootConfig()
    df = pl.DataFrame({"prediction": [0.1], "position": [1], "position_delta": [1.0]})

    with pytest.raises(RuntimeError, match="train predictions only"):
        build_final_threshold_used_row(
            run_id="run_test",
            profile="p",
            symbol="ES",
            split=1,
            config=cfg,
            train_predictions=[0.1],
            train_abs_prediction_quantile=0.1,
            threshold=0.1,
            test_result=df,
            calibration_source="test",
        )


def test_final_threshold_profile_comparison_handles_p995_vs_p999(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = RootConfig()
    cfg.execution.threshold_mode = "prediction_abs_quantile"
    cfg.execution.threshold_quantile = 0.999
    p999 = {
        "profile": "tier_1_final_threshold_p999_experiment",
        "run_id": "run_p999",
        "gross_pnl": 100.0,
        "net_pnl": 70.0,
        "cost_drag": 30.0,
        "cost_drag_pct_of_gross": 0.3,
        "total_turnover": 10.0,
        "active_splits": 2,
        "median_active_bar_pct": 0.001,
        "ACCEPT": 1,
        "REJECT": 89,
        "outlier_count": 0,
        "best_symbol_by_net_pnl": "CL",
        "worst_symbol_by_net_pnl": "ZN",
        "conclusion": "WEAK_ALPHA_RESEARCH_ONLY",
    }
    update_final_threshold_profile_comparison(
        comparison=p999,
        config=cfg,
        trade_audit={"profitable_min_trades_rejects": 36, "median_shortfall": 17},
    )

    cfg.execution.threshold_quantile = 0.995
    p995 = {**p999, "profile": "tier_1_final_threshold_p995_experiment", "run_id": "run_p995", "net_pnl": 80.0}
    rows = update_final_threshold_profile_comparison(
        comparison=p995,
        config=cfg,
        trade_audit={"profitable_min_trades_rejects": 20, "median_shortfall": 9},
    )

    saved = json.loads(FINAL_PROFILE_COMPARISON_JSON.read_text(encoding="utf-8"))
    assert {r["profile"] for r in rows} == {
        "tier_1_final_threshold_p999_experiment",
        "tier_1_final_threshold_p995_experiment",
    }
    assert {r["run_id"] for r in saved} == {"run_p999", "run_p995"}
    assert {r["threshold_quantile"] for r in saved} == {0.999, 0.995}
    assert all(str(r["run_id"]).startswith("run_") for r in saved)
