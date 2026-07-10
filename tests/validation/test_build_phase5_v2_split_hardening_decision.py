from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_phase5_v2_split_hardening_decision as gate


MARKETS = list(gate.EXPECTED_MARKETS)
YEARS = list(gate.EXPECTED_YEARS)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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


def _pairs() -> list[tuple[str, int]]:
    return [(market, year) for market in MARKETS for year in YEARS]


def _feature_paths() -> list[str]:
    return [f"data/feature_matrices/{market}/{year}.parquet" for market, year in _pairs()]


def _supplemental_feature_paths() -> list[str]:
    return [
        "data/feature_matrices/excluded_cols.json",
        "data/feature_matrices/feature_cols.json",
        "data/feature_matrices/metadata_cols.json",
        "data/feature_matrices/target_cols.json",
    ]


def _label_paths() -> list[str]:
    return [f"data/labeled/{market}/{year}.parquet" for market, year in _pairs()]


def _hash_for(index: int) -> str:
    return f"{index + 1:064x}"[-64:]


def _split_plan() -> dict[str, object]:
    input_hashes = {path: _hash_for(index) for index, path in enumerate(_feature_paths())}
    return {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/feature_matrices",
        "markets": MARKETS,
        "years": YEARS,
        "fold_count": 48,
        "failure_count": 0,
        "purge_policy": {
            "purge_bars": 61,
            "resolved_purge_bars": 61,
            "embargo_bars": 61,
        },
        "input_file_hashes": input_hashes,
        "folds": [{"fold_id": f"fold_{index:02d}"} for index in range(48)],
    }


def _split_acceptance() -> dict[str, object]:
    return {
        "status": "PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "warning_count": 0,
            "fold_count": 48,
            "prediction_file_count": 0,
        },
    }


def _contamination_audit() -> dict[str, object]:
    return {
        "status": "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD",
        "summary": {
            "classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
            "fold_count": 48,
            "valid_for_independent_holdout_claims": False,
            "valid_for_same_fold_rolling_retraining_research_evidence": True,
            "warning_count": 2,
        },
        "warnings": [
            "embargo_and_later_fold_oos_reuse_classification: "
            "WARN_EXPECTED_ROLLING_RETRAINING_REUSE; "
            "WARN_ROLLING_RETRAINING_PRIOR_EMBARGO_REUSE",
            "validation_window_presence: WARN_NO_INNER_VALIDATION_WINDOW",
        ],
    }


def _feature_manifest() -> dict[str, object]:
    return {
        "status": "PASS",
        "failure_count": 0,
        "warning_count": 0,
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "output_root": "data/feature_matrices",
        "feature_count": 114,
        "outputs": [
            {"market": market, "year": year, "status": "PASS"}
            for market, year in _pairs()
        ],
    }


def _feature_hashes() -> dict[str, object]:
    paths = _feature_paths() + _supplemental_feature_paths()
    return {
        "active_root": "data/feature_matrices",
        "failures": [],
        "active_tree_hashes_after": {path: _hash_for(index) for index, path in enumerate(paths)},
        "records": [
            {
                "path": path,
                "sha256": _hash_for(index),
                "staged_sha256": _hash_for(index),
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            }
            for index, path in enumerate(paths)
        ],
    }


def _label_hashes() -> dict[str, object]:
    paths = _label_paths()
    return {
        "active_root": "data/labeled",
        "failures": [],
        "label_semantics_id": gate.EXPECTED_LABEL_SEMANTICS_ID,
        "records": [
            {
                "active_path": path,
                "active_sha256": _hash_for(index + 100),
                "staged_sha256": _hash_for(index + 100),
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
                "market": market,
                "year": year,
            }
            for index, ((market, year), path) in enumerate(zip(_pairs(), paths))
        ],
    }


def _write_fixture(
    tmp_path: Path,
    *,
    contamination: dict[str, object] | None = None,
    feature_manifest: dict[str, object] | None = None,
    feature_hashes: dict[str, object] | None = None,
    label_hashes: dict[str, object] | None = None,
    resolved_purge_bars: int = 61,
) -> dict[str, Path]:
    paths = {
        "split_plan": tmp_path / "reports" / "wfa" / "split" / "split_plan.json",
        "split_acceptance": tmp_path / "reports" / "wfa" / "split" / "split_plan_acceptance_report.json",
        "contamination": tmp_path / "reports" / "wfa" / "contamination" / "wfa_split_contamination_audit.json",
        "feature_manifest": tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        "feature_hashes": tmp_path / "reports" / "features" / "post_active_feature_hashes.json",
        "label_hashes": tmp_path / "reports" / "labels" / "post_replacement_hashes.json",
        "models_config": tmp_path / "configs" / "models.yaml",
        "reports_root": tmp_path / "reports" / "wfa" / "split_hardening",
    }
    _write_json(paths["split_plan"], _split_plan())
    _write_json(paths["split_acceptance"], _split_acceptance())
    _write_json(paths["contamination"], contamination or _contamination_audit())
    _write_json(paths["feature_manifest"], feature_manifest or _feature_manifest())
    _write_json(paths["feature_hashes"], feature_hashes or _feature_hashes())
    _write_json(paths["label_hashes"], label_hashes or _label_hashes())
    _write_models_config(paths["models_config"], resolved_purge_bars=resolved_purge_bars)
    return paths


def _build_report(paths: dict[str, Path]) -> dict[str, object]:
    return gate.build_report(
        repo_root=paths["split_plan"].parents[3],
        split_plan_path=paths["split_plan"],
        split_acceptance_path=paths["split_acceptance"],
        contamination_audit_path=paths["contamination"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        models_config_path=paths["models_config"],
        reports_root=paths["reports_root"],
        markets=MARKETS,
        years=YEARS,
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_pass_current_style_evidence_reports_feasible_design_but_no_split_build(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)

    report = _build_report(paths)

    assert report["status"] == gate.PASS_STATUS
    summary = report["summary"]
    assert summary["current_split_allowed_use"] == "same_fold_rolling_retraining_research_only"
    assert summary["current_split_independent_holdout_allowed"] is False
    assert summary["prediction_materialization_allowed"] is False
    assert summary["phase8_refresh_allowed"] is False
    assert summary["hardened_split_generation_allowed"] is False
    assert summary["hardened_split_design_feasible"] is True
    assert summary["split_plan_generated"] is False
    assert report["hardened_design_recommendation"] is not None
    hash_check = next(
        check for check in report["checks"] if check["name"] == "active_label_feature_hash_evidence_present"
    )
    assert hash_check["observed"]["feature_market_year_record_count"] == 8
    assert hash_check["observed"]["supplemental_feature_record_count"] == 4


def test_main_writes_only_decision_reports_and_no_split_plan(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)

    exit_code = gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--split-plan",
            str(paths["split_plan"]),
            "--split-acceptance",
            str(paths["split_acceptance"]),
            "--contamination-audit",
            str(paths["contamination"]),
            "--feature-manifest",
            str(paths["feature_manifest"]),
            "--feature-placement-hashes",
            str(paths["feature_hashes"]),
            "--label-placement-hashes",
            str(paths["label_hashes"]),
            "--models-config",
            str(paths["models_config"]),
            "--reports-root",
            str(paths["reports_root"]),
        ]
    )

    assert exit_code == 0
    output_names = sorted(path.name for path in paths["reports_root"].iterdir())
    assert output_names == [gate.REPORT_JSON, gate.REPORT_MD]
    assert not (paths["reports_root"] / "split_plan.json").exists()
    assert not (paths["reports_root"] / "split_plan.csv").exists()


def test_fails_when_contamination_audit_has_failures(tmp_path: Path) -> None:
    contamination = copy.deepcopy(_contamination_audit())
    contamination["summary"]["failure_count"] = 1
    paths = _write_fixture(tmp_path, contamination=contamination)

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("contamination failure_count" in failure for failure in report["failures"])


def test_fails_when_contamination_audit_claims_independent_holdout_allowed(tmp_path: Path) -> None:
    contamination = copy.deepcopy(_contamination_audit())
    contamination["summary"]["valid_for_independent_holdout_claims"] = True
    paths = _write_fixture(tmp_path, contamination=contamination)

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("independent holdout" in failure for failure in report["failures"])


def test_fails_when_oos_embargo_reuse_warning_is_missing(tmp_path: Path) -> None:
    contamination = copy.deepcopy(_contamination_audit())
    contamination["warnings"] = ["validation_window_presence: WARN_NO_INNER_VALIDATION_WINDOW"]
    paths = _write_fixture(tmp_path, contamination=contamination)

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("WARN_EXPECTED_ROLLING_RETRAINING_REUSE" in failure for failure in report["failures"])


def test_fails_when_feature_manifest_scope_count_or_status_mismatches(tmp_path: Path) -> None:
    manifest = copy.deepcopy(_feature_manifest())
    manifest["status"] = "WARN"
    manifest["feature_count"] = 113
    paths = _write_fixture(tmp_path, feature_manifest=manifest)

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("feature manifest" in failure or "feature_count" in failure for failure in report["failures"])


def test_fails_when_label_or_feature_hash_evidence_is_missing(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    paths["label_hashes"] = tmp_path / "missing_label_hashes.json"

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("required_evidence_files_readable" in failure for failure in report["failures"])


def test_fails_when_models_purge_resolves_below_61(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, resolved_purge_bars=60)

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("resolved_purge_bars" in failure or "resolved purge" in failure for failure in report["failures"])


def test_fails_when_reports_root_contains_split_plan_outputs(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    _write_json(paths["reports_root"] / "split_plan.json", {"unexpected": True})

    report = _build_report(paths)

    assert report["status"] == gate.FAIL_STATUS
    assert any("split-plan outputs" in failure for failure in report["failures"])
