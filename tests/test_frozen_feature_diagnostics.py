import json
from pathlib import Path

import polars as pl

from pipeline.common.config import DataSectionConfig, RootConfig
from pipeline.validation.frozen_feature_diagnostics import (
    CANDIDATE_COVERAGE_JSON,
    FROZEN_FEATURE_AUDIT_JSON,
    SELECTION_SENSITIVITY_JSON,
    write_frozen_feature_diagnostics,
)


def _cfg(root: Path) -> RootConfig:
    cfg = RootConfig(symbols=["ES"], start_year=2025, end_year=2025, data=DataSectionConfig(root=str(root)))
    cfg.discovery.max_selected_features = 4
    return cfg


def _write_matrix(root: Path) -> None:
    df = pl.DataFrame(
        {
            "ts_event": pl.datetime_range(
                start=__import__("datetime").datetime(2025, 1, 1),
                end=__import__("datetime").datetime(2025, 1, 10),
                interval="1d",
                eager=True,
            ),
            "open": [1.0] * 10,
            "close": [1.0 + i for i in range(10)],
            "volume": [100.0] * 10,
            "target_15m_ret": [float((i % 3) - 1) for i in range(10)],
            "ret_lag_1": [float((i % 3) - 1) for i in range(10)],
            "roll_vol_5": [float(i) for i in range(10)],
            "roll_volume_5": [1.0] * 10,
            "roll_range_1": [None if i < 2 else float(i) for i in range(10)],
            "future_bad": [float(i) for i in range(10)],
        }
    )
    path = root / "ES" / "2025.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def _write_frozen(root: Path) -> None:
    out = root / "data/frozen_features/phase5_v1"
    out.mkdir(parents=True, exist_ok=True)
    features = ["roll_range_1", "roll_vol_5", "roll_volume_5", "ret_lag_1"]
    (out / "feature_cols.json").write_text(json.dumps({"feature_cols": features}), encoding="utf-8")
    (out / "selected_features.csv").write_text(
        "feature,rank,reason,score\n"
        "roll_range_1,1,selected_train_abs_corr,0.4\n"
        "roll_vol_5,2,selected_train_abs_corr,0.3\n"
        "roll_volume_5,3,selected_train_abs_corr,0.2\n"
        "ret_lag_1,4,selected_train_abs_corr,0.1\n",
        encoding="utf-8",
    )
    (out / "rejected_features.csv").write_text("feature,reason,score\nfuture_bad,excluded_leakage,1.0\nmissing_feature,missing_from_matrix,\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"train_only": True, "leakage_check": "PASS"}), encoding="utf-8")


def test_frozen_audit_includes_all_selected_features(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    matrix = tmp_path / "data/feature_matrices/expanded"
    _write_matrix(matrix)
    _write_frozen(tmp_path)

    result = write_frozen_feature_diagnostics(config=_cfg(matrix), source_feature_matrix_root=matrix)
    rows = json.loads(FROZEN_FEATURE_AUDIT_JSON.read_text(encoding="utf-8"))

    selected = {r["feature"] for r in rows if r["selection_status"] == "selected"}
    assert selected == {"roll_range_1", "roll_vol_5", "roll_volume_5", "ret_lag_1"}
    assert result["selected_count"] == 4


def test_rejected_leakage_features_cannot_appear_selected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    matrix = tmp_path / "data/feature_matrices/expanded"
    _write_matrix(matrix)
    _write_frozen(tmp_path)

    write_frozen_feature_diagnostics(config=_cfg(matrix), source_feature_matrix_root=matrix)
    rows = json.loads(FROZEN_FEATURE_AUDIT_JSON.read_text(encoding="utf-8"))
    future = next(r for r in rows if r["feature"] == "future_bad")

    assert future["selection_status"] == "rejected"
    assert future["leakage_flag"] is True


def test_candidate_coverage_detects_missing_and_zero_variance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    matrix = tmp_path / "data/feature_matrices/expanded"
    _write_matrix(matrix)
    _write_frozen(tmp_path)

    write_frozen_feature_diagnostics(config=_cfg(matrix), source_feature_matrix_root=matrix)
    rows = {r["feature"]: r for r in json.loads(CANDIDATE_COVERAGE_JSON.read_text(encoding="utf-8"))}

    assert rows["missing_feature"]["exists_in_matrix"] is False
    assert rows["roll_volume_5"]["zero_variance_flag"] is True
    assert float(rows["roll_range_1"]["missing_pct"]) > 0


def test_sensitivity_report_does_not_change_frozen_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    matrix = tmp_path / "data/feature_matrices/expanded"
    _write_matrix(matrix)
    _write_frozen(tmp_path)
    before = Path("data/frozen_features/phase5_v1/feature_cols.json").read_text(encoding="utf-8")

    write_frozen_feature_diagnostics(config=_cfg(matrix), source_feature_matrix_root=matrix)
    after = Path("data/frozen_features/phase5_v1/feature_cols.json").read_text(encoding="utf-8")
    sensitivity = json.loads(SELECTION_SENSITIVITY_JSON.read_text(encoding="utf-8"))

    assert before == after
    assert {r["scenario"] for r in sensitivity} == {"top_4", "top_8", "top_16", "top_32", "all_passed_stability"}
