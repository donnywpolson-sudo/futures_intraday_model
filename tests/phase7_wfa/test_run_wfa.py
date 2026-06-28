from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from sklearn.exceptions import ConvergenceWarning

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.phase7_wfa.run_wfa as wfa
from scripts.phase7_wfa.run_wfa import PREDICTION_COLUMNS, run_wfa as _run_wfa
from scripts.profile_scope import load_profile_scope, profile_config_hash
from scripts.validation.data_audit_universe_guard import load_data_audit_universe


def run_wfa(**kwargs: object) -> dict[str, object]:
    kwargs.setdefault("write_predictions", True)
    return _run_wfa(**kwargs)  # type: ignore[arg-type]


def _write_models_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
  hyperparameter_tuning_allowed_initially: false
models:
  ridge_return_v1:
    stage: phase_7a_linear_controls
    family: ridge_regression
    task: regression
    target: target_ret_15m
    enabled: true
    requires_optional_dependency: false
  logistic_direction_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_sign_with_deadzone
    enabled: true
    requires_optional_dependency: false
  logistic_fade_success_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_fade_success_15m
    enabled: true
    requires_optional_dependency: false
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_feature_matrix(root: Path, *, market: str = "ES", year: int = 2024) -> Path:
    feature_cols = ["feature_train_only_marker", "feature_signal", "feature_fade_signal"]
    root.mkdir(parents=True, exist_ok=True)
    (root / "feature_cols.json").write_text(json.dumps(feature_cols), encoding="utf-8")

    ts = pd.date_range(f"{year}-01-01T00:00:00Z", periods=72, freq="h")
    train_cutoff = pd.Timestamp(f"{year}-01-03T00:00:00Z")
    train_marker = [10.0 if value < train_cutoff else 1000.0 for value in ts]
    signal = [float(idx % 3) for idx in range(len(ts))]
    fade_signal = [float(idx % 2) for idx in range(len(ts))]
    target_sign = [-1, 0, 1] * 24
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": year,
            "session_id": "session",
            "session_segment_id": "segment",
            "causal_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
            "training_row_valid": True,
            "close": 100.0,
            "target_entry_ts": ts + pd.Timedelta(minutes=1),
            "target_exit_ts": ts + pd.Timedelta(minutes=16),
            "target_entry_price": 100.25,
            "target_exit_price": 100.50,
            "minutes_until_session_close": 60.0,
            "target_ret_15m": [value * 0.001 for value in signal],
            "target_sign_with_deadzone": target_sign,
            "target_fade_success_15m": [idx % 2 == 0 for idx in range(len(ts))],
            "fade_long_success_15m": [idx % 2 == 0 for idx in range(len(ts))],
            "fade_short_success_15m": False,
            "feature_train_only_marker": train_marker,
            "feature_signal": signal,
            "feature_fade_signal": fade_signal,
        }
    ).to_parquet(path, index=False)
    return path


def _write_feature_set(
    path: Path,
    *,
    features: list[str],
    status: str = "FROZEN",
    allowed_for_wfa: bool = True,
    feature_cols_path: Path | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": 1,
        "feature_set_id": "fixture_feature_set",
        "status": status,
        "allowed_for_wfa": allowed_for_wfa,
        "feature_count": len(features),
        "features": features,
    }
    if feature_cols_path is not None:
        payload["feature_cols_path"] = feature_cols_path.as_posix()
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_tier1_feature_set(tmp_path: Path, *, features: list[str] | None = None) -> Path:
    return _write_feature_set(
        tmp_path / "manifests" / "feature_sets" / "tier1_fixture_feature_set.json",
        features=features
        or ["feature_train_only_marker", "feature_signal", "feature_fade_signal"],
    )


def _write_profile_config(
    path: Path,
    *,
    profile: str = "fixture",
    resolved_profile: str = "fixture",
    markets: list[str] | None = None,
    years: list[int] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    alias_block = f"aliases:\n  {profile}: {resolved_profile}\n" if profile != resolved_profile else "aliases: {}\n"
    path.write_text(
        (
            "profile_defaults:\n"
            "  smoke:\n"
            "    train_days: 1\n"
            "    test_days: 1\n"
            "    step_days: 1\n"
            "profiles:\n"
            f"  {resolved_profile}:\n"
            "    settings_profile: smoke\n"
            f"    markets: {json.dumps(markets or ['ES'])}\n"
            f"    years: {json.dumps(years or [2024])}\n"
            f"{alias_block}"
        ),
        encoding="utf-8",
    )
    return path


def _feature_root(tmp_path: Path) -> Path:
    return tmp_path / "data" / "feature_matrices" / "baseline"


def _write_split_plan(
    path: Path,
    *,
    profile: str = "fixture",
    resolved_profile: str = "fixture",
    split_group: str = "research",
    selection_allowed: bool | None = True,
    include_final_holdout_flag: bool = True,
    markets: list[str] | None = None,
    years: list[int] | None = None,
    data_audit_universe: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    root = path.parents[2]
    actual_markets = markets or ["ES"]
    actual_years = years or [2024]
    profile_config = _write_profile_config(
        root / "configs" / "alpha_tiered.yaml",
        profile=profile,
        resolved_profile=resolved_profile,
        markets=actual_markets,
        years=actual_years,
    )
    models_config = root / "configs" / "models.yaml"
    final_holdout = split_group == "final_holdout"
    path.write_text(
        json.dumps(
            {
                "profile": profile,
                "resolved_profile": resolved_profile,
                "config_hash": profile_config_hash([profile_config, models_config]),
                "script_hash": "fixture-script-hash",
                "input_file_hashes": {},
                "markets": actual_markets,
                "years": actual_years,
                "data_audit_universe": data_audit_universe,
                "folds": [
                    {
                        "market": "ES",
                        "fold_id": f"ES_{split_group}_0001",
                        "split_group": split_group,
                        "train_start": "2024-01-01T00:00:00+00:00",
                        "purged_train_end": "2024-01-02T23:00:00+00:00",
                        "test_start": "2024-01-03T00:00:00+00:00",
                        "test_end": "2024-01-03T23:00:00+00:00",
                        **(
                            {"is_final_holdout": final_holdout, "final_holdout": final_holdout}
                            if include_final_holdout_flag
                            else {}
                        ),
                        **(
                            {"selection_allowed": selection_allowed}
                            if selection_allowed is not None
                            else {}
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_data_audit_universe(
    path: Path,
    *,
    audit_status: str,
    market: str = "ES",
    year: int = 2024,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "summary": {"audit_status_counts": {audit_status: 1}},
                "market_years": [
                    {
                        "market": market,
                        "year": year,
                        "audit_status": audit_status,
                        "reason": "fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_multi_data_audit_universe(
    path: Path,
    *,
    markets: list[str],
    year: int,
    audit_status: str = "usable",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "market": market,
            "year": year,
            "audit_status": audit_status,
            "usable_for_wfa": audit_status == "usable",
            "final_decision": "usable_no_synthetic_gaps_detected",
            "reason": "fixture",
        }
        for market in markets
    ]
    path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "summary": {"audit_status_counts": {audit_status: len(rows)}},
                "market_years": rows,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_scope_guard_split_plan(
    path: Path,
    *,
    profile: str = "tier_1",
    resolved_profile: str = "tier_1_research",
    markets: list[str],
    years: list[int],
    models_config: Path,
    profile_config: Path = Path("configs/alpha_tiered.yaml"),
    data_audit_universe: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "profile": profile,
                "resolved_profile": resolved_profile,
                "config_hash": profile_config_hash([profile_config, models_config]),
                "script_hash": "fixture-script-hash",
                "input_file_hashes": {},
                "markets": markets,
                "years": years,
                "data_audit_universe": data_audit_universe,
                "folds": [
                    {
                        "market": market,
                        "fold_id": f"{market}_research_0001",
                        "split_group": "research",
                        "train_start": "2023-01-01T00:00:00+00:00",
                        "purged_train_end": "2024-01-02T23:00:00+00:00",
                        "test_start": "2024-01-03T00:00:00+00:00",
                        "test_end": "2024-01-03T23:00:00+00:00",
                        "is_final_holdout": False,
                        "final_holdout": False,
                        "selection_allowed": True,
                    }
                    for market in markets
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _run_scope_guard(
    tmp_path: Path,
    *,
    requested_profile: str,
    split_markets: list[str],
    split_years: list[int],
    split_profile: str = "tier_1",
    split_resolved_profile: str = "tier_1_research",
) -> None:
    input_root = _feature_root(tmp_path)
    (input_root / "feature_cols.json").parent.mkdir(parents=True, exist_ok=True)
    (input_root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    feature_set = (
        _write_tier1_feature_set(tmp_path)
        if requested_profile in {"tier_1", "tier_1_research"}
        else None
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_scope_guard_split_plan(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        profile=split_profile,
        resolved_profile=split_resolved_profile,
        markets=split_markets,
        years=split_years,
        models_config=models_config,
    )
    run_wfa(
        profile=requested_profile,
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=tmp_path / "data" / "predictions",
        reports_root=tmp_path / "reports" / "wfa",
        models_config=models_config,
        profile_config=Path("configs/alpha_tiered.yaml"),
        feature_set_path=feature_set,
    )


def test_run_wfa_writes_oos_predictions_and_manifest(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    prediction_path = predictions_root / "baseline" / "oos_predictions.parquet"
    report_path = reports_root / "baseline_wfa_report.json"
    manifest_path = reports_root / "baseline_predictions_manifest.json"
    predictions = pd.read_parquet(prediction_path)

    assert manifest["failure_count"] == 0
    assert manifest["input_root"] == input_root.as_posix()
    assert manifest["output_root"] == predictions_root.as_posix()
    assert manifest["prediction_count"] == 72
    assert manifest["prediction_writes_enabled"] is True
    assert manifest["prediction_artifact_written"] is True
    assert manifest["prediction_artifact_write_skipped"] is False
    assert manifest["artifact_evidence_ready"] is True
    assert manifest["artifact_evidence_failures"] == []
    assert manifest["data_audit_universe"] is None
    assert manifest["feature_set"] is None
    assert manifest["stale_output_path_exists"] is False
    assert set(PREDICTION_COLUMNS).issubset(predictions.columns)
    assert len(predictions) == 24 * 3
    assert predictions["timestamp"].min() >= pd.Timestamp("2024-01-03T00:00:00Z")
    assert predictions["timestamp"].max() <= pd.Timestamp("2024-01-03T23:00:00Z")
    assert not predictions.duplicated(
        subset=["market", "timestamp", "fold_id", "model_id", "target_name"]
    ).any()
    assert report_path.exists()
    assert manifest_path.exists()
    assert manifest["output_file_hashes"][prediction_path.as_posix()] != "MISSING"


def test_prediction_cli_defaults_are_report_only_and_explicit_write_opt_in(
    tmp_path: Path,
) -> None:
    parser = wfa.build_arg_parser()

    default_args = parser.parse_args([])
    assert default_args.write_predictions is False
    assert default_args.predictions_root is None
    assert parser.parse_args(["--no-predictions"]).write_predictions is False
    assert parser.parse_args(["--report-only"]).write_predictions is False
    write_args = parser.parse_args(
        [
            "--write-predictions",
            "--predictions-root",
            (tmp_path / "reports" / "wfa_predictions").as_posix(),
        ]
    )
    assert write_args.write_predictions is True
    assert write_args.predictions_root == (
        tmp_path / "reports" / "wfa_predictions"
    ).as_posix()


def test_main_write_predictions_requires_explicit_predictions_root(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["run_wfa.py", "--write-predictions"])

    with pytest.raises(SystemExit) as excinfo:
        wfa.main()

    assert excinfo.value.code == 2
    assert (
        "--predictions-root is required when --write-predictions is set"
        in capsys.readouterr().err
    )


def test_run_wfa_report_only_writes_reports_without_prediction_file(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "feature_matrices" / "baseline_tier1_rebuild_v1"
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        write_predictions=False,
    )

    prediction_path = predictions_root / "baseline" / "oos_predictions.parquet"
    report_path = reports_root / "baseline_wfa_report.json"
    manifest_path = reports_root / "baseline_predictions_manifest.json"

    assert manifest["failure_count"] == 0
    assert manifest["prediction_count"] == 72
    assert manifest["prediction_writes_enabled"] is False
    assert manifest["prediction_artifact_written"] is False
    assert manifest["prediction_artifact_write_skipped"] is True
    assert manifest["output_root"] is None
    assert manifest["predictions_root"] is None
    assert manifest["prediction_path"] is None
    assert manifest["output_file_hashes"] == {}
    assert manifest["stale_output_path_exists"] is False
    assert manifest["artifact_evidence_ready"] is True
    assert manifest["artifact_evidence_failures"] == []
    assert report_path.exists()
    assert manifest_path.exists()
    assert not prediction_path.exists()
    assert not predictions_root.exists()


def test_report_only_rejects_stale_default_feature_root(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    with pytest.raises(SystemExit, match="refused data/feature_matrices/baseline"):
        run_wfa(
            profile="fixture",
            matrix="baseline",
            run="baseline",
            input_root=input_root,
            split_plan=split_plan,
            predictions_root=predictions_root,
            reports_root=reports_root,
            models_config=models_config,
            write_predictions=False,
        )

    assert not predictions_root.exists()


def test_run_wfa_accepts_frozen_feature_set_manifest(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)
    feature_set = _write_feature_set(
        tmp_path / "manifests" / "feature_sets" / "fixture_feature_set.json",
        features=["feature_signal", "feature_fade_signal"],
    )

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="feature_set_run",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        feature_set_path=feature_set,
    )

    predictions = pd.read_parquet(predictions_root / "feature_set_run" / "oos_predictions.parquet")

    assert manifest["failure_count"] == 0
    assert manifest["feature_count"] == 2
    assert manifest["feature_set"]["feature_set_id"] == "fixture_feature_set"
    assert manifest["feature_set"]["status"] == "FROZEN"
    assert manifest["feature_config_hash"] == wfa._file_hash_or_missing(feature_set)
    assert set(predictions["feature_config_hash"]) == {manifest["feature_config_hash"]}


def test_feature_set_rejects_non_frozen_manifest(tmp_path: Path) -> None:
    feature_set = _write_feature_set(
        tmp_path / "manifests" / "feature_sets" / "candidate.json",
        features=["feature_signal"],
        status="CANDIDATE",
    )

    with pytest.raises(SystemExit, match="not FROZEN"):
        wfa.load_feature_set(feature_set)


@pytest.mark.parametrize(
    "forbidden_feature",
    [
        "future_return_15m",
        "path_mfe_ticks_15m",
        "cost_dollars",
        "pnl",
        "execution_open",
        "entry_price",
        "exit_price",
        "trend_danger_up_30m",
        "label_semantics",
        "feature_future_return_15m",
    ],
)
def test_feature_set_rejects_forbidden_leakage_columns(
    tmp_path: Path,
    forbidden_feature: str,
) -> None:
    feature_set = _write_feature_set(
        tmp_path / "manifests" / "feature_sets" / "frozen.json",
        features=["feature_signal", forbidden_feature],
    )

    with pytest.raises(SystemExit, match="forbidden columns"):
        wfa.load_feature_set(feature_set)


def test_feature_set_rejects_feature_cols_override_together(tmp_path: Path) -> None:
    feature_set = _write_feature_set(
        tmp_path / "manifests" / "feature_sets" / "frozen.json",
        features=["feature_signal"],
    )

    with pytest.raises(SystemExit, match="provide either --feature-cols or --feature-set"):
        wfa.resolve_feature_set(
            tmp_path / "data" / "feature_matrices" / "baseline",
            feature_cols_path=tmp_path / "feature_cols.json",
            feature_set_path=feature_set,
        )


def test_scope_guard_rejects_tier2_request_with_tier1_split_plan(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None

    with pytest.raises(SystemExit) as excinfo:
        _run_scope_guard(
            tmp_path,
            requested_profile="tier_2_research",
            split_markets=scope.markets,
            split_years=scope.years,
        )

    message = str(excinfo.value)
    assert "reason=profile mismatch" in message
    assert "requested_profile='tier_2_research'" in message
    assert "requested_resolved_profile='tier_2_research'" in message
    assert "split_plan_profile='tier_1'" in message
    assert "split_plan_resolved_profile='tier_1_research'" in message
    assert "expected_markets=" in message
    assert "actual_markets=" in message
    assert "expected_years=" in message
    assert "actual_years=" in message


def test_scope_guard_rejects_tier1_split_plan_missing_market(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None

    with pytest.raises(SystemExit) as excinfo:
        _run_scope_guard(
            tmp_path,
            requested_profile="tier_1",
            split_markets=scope.markets[:-1],
            split_years=scope.years,
        )

    assert "reason=markets mismatch" in str(excinfo.value)


def test_scope_guard_rejects_tier1_split_plan_extra_market(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None

    with pytest.raises(SystemExit) as excinfo:
        _run_scope_guard(
            tmp_path,
            requested_profile="tier_1",
            split_markets=[*scope.markets, "NQ"],
            split_years=scope.years,
        )

    assert "reason=markets mismatch" in str(excinfo.value)


def test_scope_guard_rejects_tier1_split_plan_missing_year(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None

    with pytest.raises(SystemExit) as excinfo:
        _run_scope_guard(
            tmp_path,
            requested_profile="tier_1",
            split_markets=scope.markets,
            split_years=scope.years[:-1],
        )

    assert "reason=years mismatch" in str(excinfo.value)


def test_scope_guard_rejects_tier1_split_plan_extra_year(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None

    with pytest.raises(SystemExit) as excinfo:
        _run_scope_guard(
            tmp_path,
            requested_profile="tier_1",
            split_markets=scope.markets,
            split_years=[*scope.years, 2025],
        )

    assert "reason=years mismatch" in str(excinfo.value)


def test_scope_guard_rejects_split_plan_missing_provenance(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = _feature_root(tmp_path)
    (input_root / "feature_cols.json").parent.mkdir(parents=True, exist_ok=True)
    (input_root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    feature_set = _write_tier1_feature_set(tmp_path)
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_scope_guard_split_plan(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        markets=scope.markets,
        years=scope.years,
        models_config=models_config,
    )
    payload = json.loads(split_plan.read_text(encoding="utf-8"))
    payload.pop("config_hash")
    split_plan.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        run_wfa(
            profile="tier_1",
            matrix="baseline",
            run="baseline",
            input_root=input_root,
            split_plan=split_plan,
            predictions_root=tmp_path / "data" / "predictions",
            reports_root=tmp_path / "reports" / "wfa",
            models_config=models_config,
            profile_config=Path("configs/alpha_tiered.yaml"),
            feature_set_path=feature_set,
        )

    assert "reason=missing provenance field config_hash" in str(excinfo.value)


def test_scope_guard_rejects_split_plan_stale_config_hash(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = _feature_root(tmp_path)
    (input_root / "feature_cols.json").parent.mkdir(parents=True, exist_ok=True)
    (input_root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    feature_set = _write_tier1_feature_set(tmp_path)
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_scope_guard_split_plan(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        markets=scope.markets,
        years=scope.years,
        models_config=models_config,
    )
    payload = json.loads(split_plan.read_text(encoding="utf-8"))
    payload["config_hash"] = "stale"
    split_plan.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        run_wfa(
            profile="tier_1",
            matrix="baseline",
            run="baseline",
            input_root=input_root,
            split_plan=split_plan,
            predictions_root=tmp_path / "data" / "predictions",
            reports_root=tmp_path / "reports" / "wfa",
            models_config=models_config,
            profile_config=Path("configs/alpha_tiered.yaml"),
            feature_set_path=feature_set,
        )

    assert "reason=config_hash mismatch" in str(excinfo.value)


def test_valid_tier1_split_plan_passes_scope_guard(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_multi_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        markets=scope.markets,
        year=scope.years[-1],
    )
    split_plan = _write_scope_guard_split_plan(
        reports_root / "split_plan.json",
        markets=scope.markets,
        years=scope.years,
        models_config=models_config,
        data_audit_universe=load_data_audit_universe(data_audit).evidence(),
    )
    _write_feature_matrix(input_root, market=scope.markets[0], year=scope.years[0])
    _write_feature_matrix(input_root, market=scope.markets[0], year=scope.years[1])
    feature_set = _write_tier1_feature_set(tmp_path)

    manifest = run_wfa(
        profile="tier_1",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        profile_config=Path("configs/alpha_tiered.yaml"),
        feature_set_path=feature_set,
        data_audit_universe_json=data_audit,
        max_folds=1,
    )

    assert manifest["failure_count"] == 0
    assert manifest["resolved_profile"] == "tier_1_research"
    assert manifest["markets"] == scope.markets
    assert manifest["years"] == scope.years
    assert manifest["data_audit_universe"]["status_counts"] == {"usable": len(scope.markets)}


def test_tier1_run_wfa_requires_feature_set_manifest(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = _feature_root(tmp_path)
    (input_root / "feature_cols.json").parent.mkdir(parents=True, exist_ok=True)
    (input_root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_multi_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        markets=scope.markets,
        year=scope.years[-1],
    )
    split_plan = _write_scope_guard_split_plan(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        markets=scope.markets,
        years=scope.years,
        models_config=models_config,
        data_audit_universe=load_data_audit_universe(data_audit).evidence(),
    )

    with pytest.raises(SystemExit, match="Tier 1 WFA execution requires --feature-set"):
        run_wfa(
            profile="tier_1",
            matrix="baseline",
            run="baseline",
            input_root=input_root,
            split_plan=split_plan,
            predictions_root=tmp_path / "data" / "predictions",
            reports_root=tmp_path / "reports" / "wfa",
            models_config=models_config,
            profile_config=Path("configs/alpha_tiered.yaml"),
            data_audit_universe_json=data_audit,
        )


def test_tier1_run_wfa_requires_data_audit_universe_json(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = _feature_root(tmp_path)
    (input_root / "feature_cols.json").parent.mkdir(parents=True, exist_ok=True)
    (input_root / "feature_cols.json").write_text(json.dumps(["feature_signal"]), encoding="utf-8")
    feature_set = _write_tier1_feature_set(tmp_path)
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_scope_guard_split_plan(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        markets=scope.markets,
        years=scope.years,
        models_config=models_config,
    )

    with pytest.raises(SystemExit, match="Tier 1 WFA execution requires --data-audit-universe-json"):
        run_wfa(
            profile="tier_1",
            matrix="baseline",
            run="baseline",
            input_root=input_root,
            split_plan=split_plan,
            predictions_root=tmp_path / "data" / "predictions",
            reports_root=tmp_path / "reports" / "wfa",
            models_config=models_config,
            profile_config=Path("configs/alpha_tiered.yaml"),
            feature_set_path=feature_set,
        )


def test_report_records_train_only_fit_window_and_feature_mean(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    report = json.loads((reports_root / "baseline_wfa_report.json").read_text(encoding="utf-8"))
    first = report["diagnostics"][0]
    assert pd.Timestamp(first["fit_ts_max"]) < pd.Timestamp(first["score_ts_min"])
    assert first["train_feature_means_sample"]["feature_train_only_marker"] == 10.0
    classifier = next(item for item in report["diagnostics"] if item["model_id"] == "logistic_direction_v1")
    assert classifier["dummy_fallback_used"] is False
    assert classifier["y_train_unique"] == 3
    assert classifier["y_train_class_counts"] == {"-1": 16, "0": 16, "1": 16}
    assert classifier["probability_std_by_column"]["p_long"] > 0.0


def test_canonical_targets_are_consumed_without_alias_materialization(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    predictions = pd.read_parquet(predictions_root / "baseline" / "oos_predictions.parquet")
    fade = predictions[predictions["target_name"] == "target_fade_success_15m"]
    assert not fade.empty
    assert set(fade["y_true"].unique()).issubset({0, 1})
    assert fade["p_fade_success"].notna().all()


@pytest.mark.parametrize("split_group", ["restricted", "forward", "final_holdout"])
def test_non_research_fold_is_not_fit_by_default(tmp_path: Path, split_group: str) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        split_group=split_group,
        selection_allowed=False,
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "no selectable research folds" in " ".join(manifest["failures"])
    assert manifest["skipped_fold_count"] == 1
    assert manifest["artifact_evidence_ready"] is False


def test_stale_split_plan_without_selection_allowed_fails(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json", selection_allowed=None)
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "missing selection_allowed" in " ".join(manifest["failures"])


def test_stale_split_plan_without_final_holdout_flag_fails(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        include_final_holdout_flag=False,
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "missing final_holdout flag" in " ".join(manifest["failures"])


def test_split_plan_missing_declared_market_fails_instead_of_single_es_fallback(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        markets=["ES", "CL"],
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "selectable research folds missing for markets: ['CL']" in " ".join(
        manifest["failures"]
    )


def test_explicit_market_filter_is_recorded_and_does_not_trigger_fallback_guard(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        markets=["ES", "CL"],
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        markets={"ES"},
    )

    assert manifest["failure_count"] == 0
    assert manifest["fold_selection"]["markets"] == ["ES"]
    assert manifest["unfiltered_selectable_fold_count"] == 1


def test_run_wfa_records_data_audit_universe_evidence(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status="usable",
    )
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        data_audit_universe=load_data_audit_universe(data_audit).evidence(),
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    report = json.loads((reports_root / "baseline_wfa_report.json").read_text(encoding="utf-8"))
    assert manifest["failure_count"] == 0
    assert manifest["data_audit_universe"]["status_counts"] == {"usable": 1}
    assert report["data_audit_universe"] == manifest["data_audit_universe"]


def test_run_wfa_blocks_unguarded_split_plan_when_data_audit_universe_is_provided(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status="usable",
    )
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] > 0
    assert "split plan missing or stale data-audit universe evidence" in " ".join(manifest["failures"])
    assert manifest["prediction_count"] == 0


@pytest.mark.parametrize("audit_status", ["quarantined", "diagnostic_only"])
def test_run_wfa_blocks_non_usable_data_audit_fold(tmp_path: Path, audit_status: str) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status=audit_status,
    )
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        data_audit_universe=load_data_audit_universe(data_audit).evidence(),
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] > 0
    assert f"audit_status={audit_status!r}" in " ".join(manifest["failures"])
    assert manifest["prediction_count"] == 0


def test_run_wfa_does_not_load_split_plan_skipped_years(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    es_path = _write_feature_matrix(input_root)
    rty_path = input_root / "RTY" / "2024.parquet"
    rty_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(es_path)
    frame["market"] = "RTY"
    frame["year"] = 2024
    frame.to_parquet(rty_path, index=False)
    split_plan = reports_root / "split_plan.json"
    split_plan.parent.mkdir(parents=True, exist_ok=True)
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        markets=["RTY"],
        years=[2010, 2024],
    )
    split_plan.write_text(
        json.dumps(
            {
                "profile": "fixture",
                "resolved_profile": "fixture",
                "config_hash": profile_config_hash([profile_config, models_config]),
                "script_hash": "fixture-script-hash",
                "input_file_hashes": {},
                "markets": ["RTY"],
                "years": [2010, 2024],
                "skipped_inputs": [
                    {
                        "market": "RTY",
                        "year": 2010,
                        "reason": "product_unavailable_before_2017",
                    }
                ],
                "folds": [
                    {
                        "market": "RTY",
                        "fold_id": "RTY_research_0001",
                        "split_group": "research",
                        "train_start": "2024-01-01T00:00:00+00:00",
                        "purged_train_end": "2024-01-02T23:00:00+00:00",
                        "test_start": "2024-01-03T00:00:00+00:00",
                        "test_end": "2024-01-03T23:00:00+00:00",
                        "is_final_holdout": False,
                        "final_holdout": False,
                        "selection_allowed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] == 0
    assert manifest["prediction_count"] == 72


def test_existing_prediction_output_is_flagged_when_current_run_writes_none(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        split_group="restricted",
        selection_allowed=False,
    )
    _write_feature_matrix(input_root)
    stale_path = predictions_root / "baseline" / "oos_predictions.parquet"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "split_group": ["restricted"],
            "model_id": ["old_model"],
            "y_pred_raw": [0.25],
        }
    ).to_parquet(stale_path, index=False)
    stale_hash = wfa._file_sha256(stale_path)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert wfa._file_sha256(stale_path) == stale_hash
    assert manifest["prediction_count"] == 0
    assert manifest["stale_output_path_exists"] is True
    assert manifest["stale_output_path"] == stale_path.as_posix()
    assert manifest["stale_output_file_hash"] == stale_hash
    assert manifest["stale_output_row_count"] == 1
    assert manifest["stale_output_split_groups"] == ["restricted"]
    assert manifest["output_file_hashes"][stale_path.as_posix()] == "NOT_WRITTEN"
    assert manifest["artifact_evidence_ready"] is False
    assert "stale prediction output exists" in " ".join(manifest["artifact_evidence_failures"])
    assert "stale prediction output exists from a previous run" in " ".join(
        manifest["failures"]
    )


@pytest.mark.parametrize("split_group", ["restricted", "forward", "final_holdout"])
def test_non_research_fold_marked_selectable_still_fails(tmp_path: Path, split_group: str) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        split_group=split_group,
        selection_allowed=True,
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    failures = " ".join(manifest["failures"])
    assert "non-research split_group" in failures
    assert "no selectable research folds" in failures
    assert manifest["skipped_fold_count"] == 1


def test_final_holdout_fold_is_not_executed_by_phase7(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(
        reports_root / "split_plan.json",
        split_group="final_holdout",
        selection_allowed=False,
    )
    _write_feature_matrix(input_root)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert manifest["prediction_count"] == 0
    assert not (predictions_root / "baseline" / "oos_predictions.parquet").exists()
    assert manifest["skipped_folds"][0]["split_group"] == "final_holdout"


def test_convergence_warning_is_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class WarningEstimator:
        def fit(self, x_train: pd.DataFrame, y_train: pd.Series) -> "WarningEstimator":
            import warnings

            warnings.warn("forced convergence", ConvergenceWarning)
            return self

    def forced_estimator(spec: object, y_train: pd.Series) -> tuple[WarningEstimator, str]:
        return WarningEstimator(), "logistic_regression"

    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    _write_feature_matrix(input_root)
    monkeypatch.setattr(wfa, "_build_estimator", forced_estimator)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "convergence warning" in " ".join(manifest["failures"])


def test_constant_classifier_probabilities_fail_without_dummy_fallback(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    predictions_root = tmp_path / "data" / "predictions"
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    split_plan = _write_split_plan(reports_root / "split_plan.json")
    path = _write_feature_matrix(input_root)
    frame = pd.read_parquet(path)
    frame["feature_signal"] = 1.0
    frame["feature_fade_signal"] = 1.0
    frame["feature_train_only_marker"] = 1.0
    frame.to_parquet(path, index=False)

    manifest = run_wfa(
        profile="fixture",
        matrix="baseline",
        run="baseline",
        input_root=input_root,
        split_plan=split_plan,
        predictions_root=predictions_root,
        reports_root=reports_root,
        models_config=models_config,
    )

    assert manifest["failure_count"] > 0
    assert "near-constant" in " ".join(manifest["failures"])
    report = json.loads((reports_root / "baseline_wfa_report.json").read_text(encoding="utf-8"))
    failed = [item for item in report["diagnostics"] if item["status"] == "FAIL"]
    assert failed
    assert failed[0]["dummy_fallback_used"] is False
    assert failed[0]["prediction_std"] <= wfa.CLASSIFIER_COLLAPSE_STD_EPS
