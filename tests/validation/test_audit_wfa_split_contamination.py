from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from scripts.validation import audit_wfa_split_contamination as guard


MARKET = "ES"
YEAR = 2024
FEATURE_COUNT = 1
FOLD_COUNT = 2


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _ts(index: int) -> str:
    base = pd.Timestamp(f"{YEAR}-01-01T00:00:00Z")
    return (base + pd.Timedelta(minutes=index)).isoformat()


def _write_models_config(path: Path, *, resolved_purge_bars: int = 61) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
purge:
  entry_lag_bars: 1
  target_horizon_bars: 30
  trend_horizon_bars: 60
  purge_bars: auto
  resolved_purge_bars: {resolved_purge_bars}
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_runner(path: Path, *, valid: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if valid:
        source = """
def run(train, test, feature_cols, estimator, y_train):
    if train["ts"].max() >= test["ts"].min():
        raise ValueError("overlap")
    x_train = train[feature_cols]
    x_test = test[feature_cols]
    estimator.fit(x_train, y_train)
    return estimator.predict(x_test)
""".strip()
    else:
        source = """
def run(frame, feature_cols, estimator, y_train):
    estimator.fit(frame[feature_cols], y_train)
""".strip()
    path.write_text(source, encoding="utf-8")
    return path


def _feature_frame(rows: int = 360) -> pd.DataFrame:
    ts = pd.Series(pd.date_range(f"{YEAR}-01-01T00:00:00Z", periods=rows, freq="min"))
    return pd.DataFrame(
        {
            "ts": ts,
            "training_row_valid": True,
            "target_30m_valid": ts.shift(-31).notna(),
            "target_60m_valid": ts.shift(-61).notna(),
            "target_exit_ts_30m": ts.shift(-31),
            "target_exit_ts_60m": ts.shift(-61),
            "target_ret_30m": 0.01,
            "feature_safe": 1.0,
        }
    )


def _split_plan(*, embargo_bars: int = 61) -> dict[str, object]:
    folds = [
        {
            "fold_id": "ES_research_0001",
            "fold_number": 1,
            "market": MARKET,
            "train_start": _ts(0),
            "train_end": _ts(121),
            "purged_train_end": _ts(60),
            "test_start": _ts(122),
            "test_end": _ts(131),
            "embargo_end": _ts(192),
            "train_rows_after_purge": 61,
            "test_rows": 10,
            "purge_bars": 61,
            "resolved_purge_bars": 61,
            "purged_train_rows": 61,
            "embargo_bars": embargo_bars,
        },
        {
            "fold_id": "ES_research_0002",
            "fold_number": 2,
            "market": MARKET,
            "train_start": _ts(0),
            "train_end": _ts(192),
            "purged_train_end": _ts(131),
            "test_start": _ts(193),
            "test_end": _ts(202),
            "embargo_end": _ts(263),
            "train_rows_after_purge": 132,
            "test_rows": 10,
            "purge_bars": 61,
            "resolved_purge_bars": 61,
            "purged_train_rows": 61,
            "embargo_bars": embargo_bars,
        },
    ]
    return {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/feature_matrices",
        "markets": [MARKET],
        "years": [YEAR],
        "fold_count": len(folds),
        "failure_count": 0,
        "purge_policy": {
            "purge_bars": 61,
            "resolved_purge_bars": 61,
            "embargo_bars": embargo_bars,
        },
        "folds": folds,
    }


def _write_fixture(
    tmp_path: Path,
    *,
    mutate_frame: Callable[[pd.DataFrame], None] | None = None,
    mutate_split: Callable[[dict[str, object]], None] | None = None,
    feature_cols: list[str] | None = None,
    manifest_status: str = "PASS",
    resolved_purge_bars: int = 61,
    runner_valid: bool = True,
) -> dict[str, Path]:
    feature_root = tmp_path / "data" / "feature_matrices"
    matrix_path = feature_root / MARKET / f"{YEAR}.parquet"
    frame = _feature_frame()
    if mutate_frame is not None:
        mutate_frame(frame)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(matrix_path, index=False)

    _write_json(feature_root / "feature_cols.json", feature_cols or ["feature_safe"])
    _write_json(
        feature_root / "target_cols.json",
        [
            "target_ret_30m",
            "target_30m_valid",
            "target_60m_valid",
            "target_exit_ts_30m",
            "target_exit_ts_60m",
        ],
    )

    split_plan = _split_plan()
    if mutate_split is not None:
        mutate_split(split_plan)
    split_path = _write_json(tmp_path / "reports" / "wfa" / "split_plan.json", split_plan)
    manifest_path = _write_json(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        {
            "status": manifest_status,
            "failure_count": 0,
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "output_root": "data/feature_matrices",
            "feature_count": FEATURE_COUNT,
            "markets": [MARKET],
            "years": [YEAR],
        },
    )
    models_config = _write_models_config(
        tmp_path / "configs" / "models.yaml",
        resolved_purge_bars=resolved_purge_bars,
    )
    runner = _write_runner(tmp_path / "scripts" / "phase7_wfa" / "run_wfa.py", valid=runner_valid)
    return {
        "feature_root": feature_root,
        "split_plan": split_path,
        "feature_manifest": manifest_path,
        "models_config": models_config,
        "runner": runner,
        "reports_root": tmp_path / "reports" / "wfa" / "contamination_audit",
        "matrix": matrix_path,
    }


def _build_report(paths: dict[str, Path], *, write_reports: bool = False) -> dict[str, object]:
    return guard.build_report(
        repo_root=paths["feature_root"].parents[1],
        split_plan_path=paths["split_plan"],
        feature_root=paths["feature_root"],
        feature_manifest_path=paths["feature_manifest"],
        models_config_path=paths["models_config"],
        wfa_runner_path=paths["runner"],
        reports_root=paths["reports_root"],
        markets=(MARKET,),
        years=(YEAR,),
        expected_feature_count=FEATURE_COUNT,
        expected_fold_count=FOLD_COUNT,
        write_reports=write_reports,
    )


def test_passes_current_style_rolling_split_with_research_only_warnings(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)

    report = _build_report(paths)

    assert report["status"] == guard.PASS_STATUS
    summary = report["summary"]
    assert summary["valid_for_independent_holdout_claims"] is False
    assert summary["valid_for_same_fold_rolling_retraining_research_evidence"] is True
    assert summary["classification"] == "same_fold_rolling_retraining_research_only"
    assert any("WARN_EXPECTED_ROLLING_RETRAINING_REUSE" in warning for warning in report["warnings"])
    assert any("WARN_NO_INNER_VALIDATION_WINDOW" in warning for warning in report["warnings"])


def test_main_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)

    exit_code = guard.main(
        [
            "--repo-root",
            str(tmp_path),
            "--split-plan",
            str(paths["split_plan"]),
            "--feature-root",
            str(paths["feature_root"]),
            "--feature-manifest",
            str(paths["feature_manifest"]),
            "--models-config",
            str(paths["models_config"]),
            "--wfa-runner",
            str(paths["runner"]),
            "--reports-root",
            str(paths["reports_root"]),
            "--markets",
            MARKET,
            "--years",
            str(YEAR),
            "--expected-feature-count",
            str(FEATURE_COUNT),
            "--expected-fold-count",
            str(FOLD_COUNT),
        ]
    )

    assert exit_code == 0
    assert (paths["reports_root"] / guard.REPORT_JSON).is_file()
    assert (paths["reports_root"] / guard.REPORT_MD).is_file()


def test_fails_when_same_fold_train_test_boundaries_overlap(tmp_path: Path) -> None:
    def mutate_split(split_plan: dict[str, object]) -> None:
        folds = split_plan["folds"]
        assert isinstance(folds, list)
        folds[0]["purged_train_end"] = folds[0]["test_start"]

    paths = _write_fixture(tmp_path, mutate_split=mutate_split)

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("train/test chronology violation" in failure for failure in report["failures"])


def test_fails_when_train_target_horizon_reaches_test_start(tmp_path: Path) -> None:
    def mutate_frame(frame: pd.DataFrame) -> None:
        frame.loc[60, "target_exit_ts_60m"] = frame.loc[122, "ts"]

    paths = _write_fixture(tmp_path, mutate_frame=mutate_frame)

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("train target horizon reaches test_start" in failure for failure in report["failures"])


def test_fails_when_purge_or_embargo_is_short(tmp_path: Path) -> None:
    def mutate_split(split_plan: dict[str, object]) -> None:
        policy = split_plan["purge_policy"]
        assert isinstance(policy, dict)
        policy["embargo_bars"] = 60
        folds = split_plan["folds"]
        assert isinstance(folds, list)
        folds[0]["embargo_bars"] = 60

    paths = _write_fixture(
        tmp_path,
        mutate_split=mutate_split,
        resolved_purge_bars=60,
    )

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("embargo" in failure or "resolved_purge_bars" in failure for failure in report["failures"])


def test_low_purged_train_rows_metadata_does_not_fail_when_target_horizon_is_clear(
    tmp_path: Path,
) -> None:
    def mutate_split(split_plan: dict[str, object]) -> None:
        folds = split_plan["folds"]
        assert isinstance(folds, list)
        for fold in folds:
            fold["purged_train_rows"] = 8

    paths = _write_fixture(tmp_path, mutate_split=mutate_split)

    report = _build_report(paths)

    assert report["status"] == guard.PASS_STATUS
    same_fold_check = next(
        check
        for check in report["checks"]
        if check["name"] == "same_fold_train_test_and_target_horizon_separation"
    )
    assert same_fold_check["evidence"]["purged_train_rows_metadata_below_dependency_count"] == 2


def test_prior_embargo_reuse_is_research_only_warning_not_same_fold_failure(
    tmp_path: Path,
) -> None:
    def mutate_split(split_plan: dict[str, object]) -> None:
        folds = split_plan["folds"]
        assert isinstance(folds, list)
        folds[1]["train_end"] = _ts(211)
        folds[1]["purged_train_end"] = _ts(150)
        folds[1]["test_start"] = _ts(212)
        folds[1]["test_end"] = _ts(221)
        folds[1]["embargo_end"] = _ts(282)

    paths = _write_fixture(tmp_path, mutate_split=mutate_split)

    report = _build_report(paths)

    assert report["status"] == guard.PASS_STATUS
    assert any("WARN_ROLLING_RETRAINING_PRIOR_EMBARGO_REUSE" in warning for warning in report["warnings"])


def test_fails_when_feature_registry_contains_target_or_forbidden_feature(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, feature_cols=["target_ret_30m"])

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("forbidden feature columns" in failure for failure in report["failures"])


def test_fails_when_feature_manifest_scope_or_status_is_bad(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, manifest_status="FAIL")

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("feature manifest status" in failure for failure in report["failures"])


def test_fails_when_runner_static_train_only_patterns_are_missing(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, runner_valid=False)

    report = _build_report(paths)

    assert report["status"] == guard.FAIL_STATUS
    assert any("missing required runner train-only patterns" in failure for failure in report["failures"])
