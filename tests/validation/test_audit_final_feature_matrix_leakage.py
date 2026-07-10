from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation.audit_final_feature_matrix_leakage import (
    build_final_feature_matrix_leakage_audit,
)


SAFE_PHASE4_SOURCE = """
def add_base_market_features(df):
    df["feature_ret_1"] = df["close"] / df["close"].shift(1) - 1.0
    return df
"""

SAFE_WFA_SOURCE = """
Pipeline([("imputer", SimpleImputer()), ("scaler", StandardScaler())])
if train["ts"].max() >= test["ts"].min():
    raise ValueError("overlap")
estimator.fit(x_train, y_train)
"""


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_sources(tmp_path: Path, *, phase4_source: str = SAFE_PHASE4_SOURCE) -> tuple[Path, Path]:
    phase4 = tmp_path / "scripts" / "phase4_features" / "build_baseline_features.py"
    wfa = tmp_path / "scripts" / "phase7_wfa" / "run_wfa.py"
    phase4.parent.mkdir(parents=True, exist_ok=True)
    wfa.parent.mkdir(parents=True, exist_ok=True)
    phase4.write_text(phase4_source, encoding="utf-8")
    wfa.write_text(SAFE_WFA_SOURCE, encoding="utf-8")
    return phase4, wfa


def _write_fixture(
    tmp_path: Path,
    *,
    feature_cols: list[str],
    target_cols: list[str] | None = None,
    phase4_source: str = SAFE_PHASE4_SOURCE,
    feature_values: dict[str, list[float]] | None = None,
    target_values: list[float] | None = None,
) -> dict[str, Path]:
    target_cols = target_cols or ["target_ret_30m"]
    feature_root = tmp_path / "data" / "feature_matrices"
    labeled_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "reports" / "audit"
    ts = pd.date_range("2024-01-02T14:30:00Z", periods=4, freq="min")
    feature_values = feature_values or {
        feature: [0.0, 0.1, 0.2, 0.1] for feature in feature_cols
    }
    frame = pd.DataFrame(
        {
            "ts": ts,
            "training_row_valid": True,
            "target_ret_30m": target_values or [10.0, 20.0, 10.0, 30.0],
            **feature_values,
        }
    )
    feature_path = feature_root / "ES" / "2024.parquet"
    label_path = labeled_root / "ES" / "2024.parquet"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(feature_path, index=False)
    pd.DataFrame({"ts": ts}).to_parquet(label_path, index=False)
    _write_json(feature_root / "feature_cols.json", feature_cols)
    _write_json(feature_root / "target_cols.json", target_cols)
    manifest = _write_json(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        {"status": "PASS", "feature_count": len(feature_cols)},
    )
    split_plan = _write_json(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        {"status": "PASS", "fold_count": 1},
    )
    phase4, wfa = _write_sources(tmp_path, phase4_source=phase4_source)
    return {
        "feature_root": feature_root,
        "labeled_root": labeled_root,
        "manifest": manifest,
        "split_plan": split_plan,
        "output_root": output_root,
        "phase4": phase4,
        "wfa": wfa,
    }


def _run_audit(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    paths = _write_fixture(tmp_path, **kwargs)
    return build_final_feature_matrix_leakage_audit(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        labeled_root=paths["labeled_root"],
        manifest_path=paths["manifest"],
        split_plan_path=paths["split_plan"],
        output_root=paths["output_root"],
        phase4_script_path=paths["phase4"],
        wfa_runner_path=paths["wfa"],
        markets=("ES",),
        years=(2024,),
        max_embedding_sample_rows_per_file=10,
        min_embedding_overlap=3,
        write_reports=True,
    )


def test_passes_causal_current_bar_features_under_completed_bar_convention(tmp_path: Path) -> None:
    report = _run_audit(tmp_path, feature_cols=["feature_ret_1"])

    assert report["status"] == "PASS"
    assert report["required_feature_removals"] == []
    assert report["matrix_file_checks"][0]["timestamp_contract_violation_count"] == 0
    assert report["confidence_score"]["score"] >= 90


def test_reports_json_and_markdown_with_required_sections(tmp_path: Path) -> None:
    report = _run_audit(tmp_path, feature_cols=["feature_ret_1"])
    outputs = report["outputs"]

    json_path = tmp_path / outputs["json"]  # type: ignore[index]
    md_path = tmp_path / outputs["markdown"]  # type: ignore[index]
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert json_path.exists()
    assert md_path.exists()
    assert "feature_risk_inventory" in payload
    assert "leakage_findings" in payload
    assert "required_feature_removals" in payload
    assert "confidence_score" in payload
    assert "# Final Feature Matrix Leakage Audit" in md_path.read_text(encoding="utf-8")


def test_fails_target_column_in_feature_cols(tmp_path: Path) -> None:
    report = _run_audit(
        tmp_path,
        feature_cols=["target_ret_30m"],
        feature_values={"target_ret_30m": [10.0, 20.0, 10.0, 30.0]},
    )

    assert report["status"] == "FAIL"
    assert "target_ret_30m" in report["required_feature_removals"]
    assert report["leakage_findings"]["target_leakage"]["status"] == "FAIL"  # type: ignore[index]


def test_constant_feature_target_match_is_not_label_embedding(tmp_path: Path) -> None:
    report = _run_audit(
        tmp_path,
        feature_cols=["feature_ret_1"],
        feature_values={"feature_ret_1": [0.0, 0.0, 0.0, 0.0]},
        target_values=[0.0, 0.0, 0.0, 0.0],
    )

    assert report["status"] == "PASS"
    assert report["leakage_findings"]["accidental_label_embedding"]["status"] == "PASS"  # type: ignore[index]


def test_fails_negative_shift_future_transform(tmp_path: Path) -> None:
    report = _run_audit(
        tmp_path,
        feature_cols=["feature_bad"],
        phase4_source='df["feature_bad"] = df["close"].shift(-1)\n',
    )

    assert report["status"] == "FAIL"
    assert "feature_bad" in report["required_feature_removals"]
    assert report["leakage_findings"]["lookahead_bias"]["status"] == "FAIL"  # type: ignore[index]


def test_fails_full_session_future_aggregate(tmp_path: Path) -> None:
    report = _run_audit(
        tmp_path,
        feature_cols=["feature_bad"],
        phase4_source='df["feature_bad"] = df.groupby("session")["high"].transform("max")\n',
    )

    assert report["status"] == "FAIL"
    assert "feature_bad" in report["required_feature_removals"]
    assert report["leakage_findings"]["lookahead_bias"]["status"] == "FAIL"  # type: ignore[index]


def test_fails_full_sample_normalization_before_wfa(tmp_path: Path) -> None:
    report = _run_audit(
        tmp_path,
        feature_cols=["feature_bad"],
        phase4_source='df["feature_bad"] = StandardScaler().fit_transform(df[["feature_bad"]])\n',
    )

    assert report["status"] == "FAIL"
    assert "feature_bad" in report["required_feature_removals"]
    assert (
        report["leakage_findings"]["feature_engineering_outside_training_windows"]["status"]  # type: ignore[index]
        == "FAIL"
    )
