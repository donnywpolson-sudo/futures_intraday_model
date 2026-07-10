from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_phase5_v2_wfa_preflight_decision as gate


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_profile_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
defaults:
  final_holdout_years: [2025]
profile_defaults:
  recent_research:
    train_days: 365
    test_days: 30
    step_days: 30
profiles:
  tier_1_research:
    intent: core_recent_research
    settings_profile: recent_research
    markets: ["ES", "CL", "ZN", "6E"]
    years: [2023, 2024]
aliases:
  tier_1: tier_1_research
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_models_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
purge:
  entry_lag_bars: 1
  target_horizon_bars: 30
  trend_horizon_bars: 60
  purge_bars: auto
  resolved_purge_bars: 61
model_selection_reports:
  final_holdout_excluded_from_selection: true
""".strip(),
        encoding="utf-8",
    )
    return path


def _feature_columns() -> list[str]:
    return [f"feature_{index:03d}" for index in range(gate.EXPECTED_FEATURE_COUNT)]


def _metadata_columns() -> list[str]:
    return list(gate.REQUIRED_FEATURE_MATRIX_COLUMNS)


def _feature_frame(market: str, year: int) -> pd.DataFrame:
    rows = 3
    payload: dict[str, object] = {
        "ts": pd.date_range(f"{year}-01-01T00:00:00Z", periods=rows, freq="min"),
        "market": [market] * rows,
        "year": [year] * rows,
        "training_row_valid": [True] * rows,
        "target_valid": [True] * rows,
        "feature_input_valid": [True] * rows,
    }
    payload.update({column: [1] * rows for column in gate.REQUIRED_V2_TARGET_COLUMNS})
    payload.update({column: [1.0] * rows for column in _feature_columns()})
    filler_count = gate.EXPECTED_FEATURE_PARQUET_COLUMNS - len(payload)
    payload.update({f"feature_matrix_extra_{index:03d}": [0] * rows for index in range(filler_count)})
    return pd.DataFrame(payload)


def _label_frame(market: str, year: int) -> pd.DataFrame:
    rows = 3
    payload: dict[str, object] = {
        "ts": pd.date_range(f"{year}-01-01T00:00:00Z", periods=rows, freq="min"),
        "market": [market] * rows,
        "year": [year] * rows,
    }
    payload.update({column: [1] * rows for column in gate.REQUIRED_V2_TARGET_COLUMNS})
    filler_count = gate.EXPECTED_LABEL_PARQUET_COLUMNS - len(payload)
    payload.update({f"label_extra_{index:03d}": [0] * rows for index in range(filler_count)})
    return pd.DataFrame(payload)


def _write_parquet(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def _write_fixture(tmp_path: Path) -> dict[str, Path]:
    feature_root = tmp_path / "data" / "feature_matrices"
    label_root = tmp_path / "data" / "labeled"
    reports_root = tmp_path / "reports" / "wfa_preflight" / "phase5_v2"
    future_root = tmp_path / "reports" / "wfa" / "phase5_v2"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    pairs = gate.expected_pairs(gate.EXPECTED_MARKETS, gate.EXPECTED_YEARS)

    output_file_hashes: dict[str, str] = {}
    feature_records: list[dict[str, object]] = []
    label_records: list[dict[str, object]] = []
    outputs: list[dict[str, object]] = []
    for market, year in pairs:
        feature_frame = _feature_frame(market, year)
        label_frame = _label_frame(market, year)
        feature_path = _write_parquet(feature_root / market / f"{year}.parquet", feature_frame)
        label_path = _write_parquet(label_root / market / f"{year}.parquet", label_frame)
        feature_rel = gate.rel(feature_path, tmp_path)
        label_rel = gate.rel(label_path, tmp_path)
        feature_hash = file_sha256(feature_path)
        label_hash = file_sha256(label_path)
        output_file_hashes[feature_rel] = feature_hash
        feature_records.append(
            {
                "path": feature_rel,
                "sha256": feature_hash,
                "staged_sha256": feature_hash,
                "backup_sha256": "backup",
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
                "rows": len(feature_frame),
                "columns": len(feature_frame.columns),
            }
        )
        label_records.append(
            {
                "active_path": label_rel,
                "active_sha256": label_hash,
                "staged_sha256": label_hash,
                "backup_sha256": "backup",
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
                "active_rows": len(label_frame),
                "active_columns": len(label_frame.columns),
                "market": market,
                "year": year,
            }
        )
        outputs.append(
            {
                "market": market,
                "year": year,
                "input_path": label_rel,
                "output_path": feature_rel,
                "input_rows": len(label_frame),
                "output_rows": len(feature_frame),
                "status": "PASS",
                "failure_count": 0,
                "failures": [],
                "warning_count": 0,
                "warnings": [],
            }
        )

    for name, payload in {
        "feature_cols.json": _feature_columns(),
        "target_cols.json": list(gate.REQUIRED_V2_TARGET_COLUMNS),
        "metadata_cols.json": _metadata_columns(),
        "excluded_cols.json": ["open", "high", "low", "close"],
    }.items():
        path = _write_json(feature_root / name, payload)
        digest = file_sha256(path)
        feature_records.append(
            {
                "path": gate.rel(path, tmp_path),
                "sha256": digest,
                "staged_sha256": digest,
                "backup_sha256": "backup",
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            }
        )

    feature_manifest = _write_json(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        {
            "status": "PASS",
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "output_root": gate.rel(feature_root, tmp_path),
            "markets": list(gate.EXPECTED_MARKETS),
            "years": list(gate.EXPECTED_YEARS),
            "feature_count": gate.EXPECTED_FEATURE_COUNT,
            "failure_count": 0,
            "failures": [],
            "warning_count": 0,
            "feature_audit_gate": {"status": "PASS", "failure_count": 0},
            "forbidden_feature_leakage_failures": [],
            "output_file_hashes": output_file_hashes,
            "outputs": outputs,
        },
    )
    feature_hashes = _write_json(
        tmp_path / "reports" / "features" / "post_active_feature_hashes.json",
        {
            "status": "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM",
            "records": feature_records,
        },
    )
    label_hashes = _write_json(
        tmp_path / "reports" / "labels" / "post_replacement_hashes.json",
        {
            "status": "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM",
            "records": label_records,
        },
    )
    universe = _write_json(
        tmp_path / "reports" / "data_audit" / "universe.json",
        {
            "status": "PASS",
            "summary": {"audit_status_counts": {"usable": len(pairs)}},
            "market_years": [
                {
                    "market": market,
                    "year": year,
                    "audit_status": "usable",
                    "final_decision": "ready_for_tier1_wfa_research_with_accepted_caveats",
                    "usable_for_wfa": True,
                    "reason": "fixture",
                }
                for market, year in pairs
            ],
        },
    )
    return {
        "feature_root": feature_root,
        "label_root": label_root,
        "feature_manifest": feature_manifest,
        "feature_hashes": feature_hashes,
        "label_hashes": label_hashes,
        "universe": universe,
        "reports_root": reports_root,
        "future_root": future_root,
        "profile_config": profile_config,
        "models_config": models_config,
    }


def _build(tmp_path: Path, **overrides: object) -> dict[str, object]:
    paths = _write_fixture(tmp_path)
    paths.update({key: value for key, value in overrides.items() if isinstance(value, Path)})
    return gate.build_report(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        label_root=paths["label_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["universe"],
        reports_root=paths["reports_root"],
        future_wfa_reports_root=paths["future_root"],
        profile_config_path=paths["profile_config"],
        models_config_path=paths["models_config"],
        markets=overrides.get("markets", list(gate.EXPECTED_MARKETS)),
        years=overrides.get("years", list(gate.EXPECTED_YEARS)),
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_pass_report_exposes_exact_future_phase5_command(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == gate.PASS_STATUS
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["split_plan_generated"] is False
    command = report["future_phase5_split_command"]
    assert command.startswith("python -m scripts.phase5_wfa.build_wfa_splits")
    assert "--profile tier_1" in command
    assert "--input-root data/feature_matrices" in command
    assert "--reports-root reports/wfa/phase5_v2" in command
    assert "--markets 6E,CL,ES,ZN" in command
    assert "--years 2023,2024" in command


def test_feature_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    payload = json.loads(paths["feature_hashes"].read_text(encoding="utf-8"))
    payload["records"][0]["sha256"] = "bad"
    paths["feature_hashes"].write_text(json.dumps(payload), encoding="utf-8")

    report = gate.build_report(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        label_root=paths["label_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["universe"],
        reports_root=paths["reports_root"],
        future_wfa_reports_root=paths["future_root"],
        profile_config_path=paths["profile_config"],
        models_config_path=paths["models_config"],
        markets=list(gate.EXPECTED_MARKETS),
        years=list(gate.EXPECTED_YEARS),
        generated_at_utc="2026-07-09T00:00:00Z",
    )

    assert report["status"] == gate.FAIL_STATUS
    assert any(
        check["name"] == "active_label_feature_hash_evidence_matches"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_data_audit_universe_missing_row_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    payload = json.loads(paths["universe"].read_text(encoding="utf-8"))
    payload["market_years"] = payload["market_years"][:-1]
    paths["universe"].write_text(json.dumps(payload), encoding="utf-8")

    report = gate.build_report(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        label_root=paths["label_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["universe"],
        reports_root=paths["reports_root"],
        future_wfa_reports_root=paths["future_root"],
        profile_config_path=paths["profile_config"],
        models_config_path=paths["models_config"],
        markets=list(gate.EXPECTED_MARKETS),
        years=list(gate.EXPECTED_YEARS),
        generated_at_utc="2026-07-09T00:00:00Z",
    )

    assert report["status"] == gate.FAIL_STATUS
    assert any(
        check["name"] == "data_audit_universe_exact_usable_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_v2_target_column_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    target_cols = json.loads((paths["feature_root"] / "target_cols.json").read_text(encoding="utf-8"))
    target_cols.remove("target_fillable_after_slippage_60m")
    (paths["feature_root"] / "target_cols.json").write_text(json.dumps(target_cols), encoding="utf-8")

    report = gate.build_report(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        label_root=paths["label_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["universe"],
        reports_root=paths["reports_root"],
        future_wfa_reports_root=paths["future_root"],
        profile_config_path=paths["profile_config"],
        models_config_path=paths["models_config"],
        markets=list(gate.EXPECTED_MARKETS),
        years=list(gate.EXPECTED_YEARS),
        generated_at_utc="2026-07-09T00:00:00Z",
    )

    assert report["status"] == gate.FAIL_STATUS
    assert any(
        check["name"] == "required_v2_targets_and_wfa_columns_present"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_scope_expansion_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, markets=["6E", "CL", "ES", "ZN", "NQ"])

    assert report["status"] == gate.FAIL_STATUS
    assert any(
        check["name"] == "exact_8_market_year_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_future_split_plan_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    _write_json(paths["future_root"] / "split_plan.json", {"status": "PASS"})

    report = gate.build_report(
        repo_root=tmp_path,
        feature_root=paths["feature_root"],
        label_root=paths["label_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["universe"],
        reports_root=paths["reports_root"],
        future_wfa_reports_root=paths["future_root"],
        profile_config_path=paths["profile_config"],
        models_config_path=paths["models_config"],
        markets=list(gate.EXPECTED_MARKETS),
        years=list(gate.EXPECTED_YEARS),
        generated_at_utc="2026-07-09T00:00:00Z",
    )

    assert report["status"] == gate.FAIL_STATUS
    assert any(
        check["name"] == "no_phase5_split_artifacts_written_or_overwritten"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
