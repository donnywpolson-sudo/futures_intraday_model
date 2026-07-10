import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.pipeline_gates import file_sha256
from scripts.profile_scope import profile_config_hash
from scripts.validation.review_phase6_wfa_runner_preflight import (
    FAIL_STATUS,
    HARDENED_SPLIT_ACCEPTANCE_STATUS,
    HARDENED_SPLIT_STATUS,
    PASS_STATUS,
    REQUIRED_V2_TARGET_COLUMNS,
    V2_LABEL_SEMANTICS_ID,
    main,
)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_parquet(
    path: Path,
    *,
    include_target: bool = True,
    extra_targets: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": pa.array([1], type=pa.int64()),
        "market": pa.array(["ES"]),
        "year": pa.array([2024], type=pa.int64()),
        "session_id": pa.array(["s1"]),
        "session_segment_id": pa.array(["rth"]),
        "causal_valid": pa.array([True]),
        "target_valid": pa.array([True]),
        "feature_input_valid": pa.array([True]),
        "training_row_valid": pa.array([True]),
        "close": pa.array([100.0]),
        "target_entry_ts": pa.array([1], type=pa.int64()),
        "target_exit_ts": pa.array([2], type=pa.int64()),
        "target_entry_price": pa.array([100.0]),
        "target_exit_price": pa.array([100.5]),
        "minutes_until_session_close": pa.array([30], type=pa.int64()),
        "feature_signal": pa.array([0.1]),
    }
    if include_target:
        payload["target_ret_15m"] = pa.array([0.005])
    for target in extra_targets or []:
        if target not in payload:
            payload[target] = pa.array([0.0])
    pq.write_table(pa.table(payload), path)


def _fixture(
    tmp_path: Path,
    *,
    include_target: bool = True,
    v2_evidence: bool = False,
    include_v2_targets: bool = True,
    profile: str = "tier_1_core",
) -> dict[str, Path]:
    repo_root = tmp_path
    feature_root = repo_root / "data/feature_matrices"
    feature_file = feature_root / "ES/2024.parquet"
    extra_targets = REQUIRED_V2_TARGET_COLUMNS if v2_evidence and include_v2_targets else []
    _write_parquet(feature_file, include_target=include_target, extra_targets=extra_targets)
    _write_json(feature_root / "feature_cols.json", ["feature_signal"])
    _write_json(feature_root / "target_cols.json", ["target_ret_15m", *extra_targets])

    profile_config = repo_root / "configs/alpha_tiered.yaml"
    _write_text(
        profile_config,
        "aliases:\n"
        f"  {profile}: tier_1_research\n"
        "profiles:\n"
        "  tier_1_research:\n"
        "    markets: [ES]\n"
        "    years: [2024]\n",
    )
    models_config = repo_root / "configs/models.yaml"
    _write_text(
        models_config,
        "policy:\n"
        "  random_splits_allowed: false\n"
        "  hyperparameter_tuning_allowed_initially: false\n"
        "  final_holdout_tuning_allowed: false\n"
        "models:\n"
        "  ridge_return_v1:\n"
        "    stage: phase_7a_linear_controls\n"
        "    family: ridge_regression\n"
        "    task: regression\n"
        "    enabled: true\n"
        "    requires_optional_dependency: false\n"
        "    target: target_ret_15m\n",
    )

    feature_manifest = (
        repo_root
        / "reports/data_audit/current_state/tier1_core_phase4/active_feature_manifest.json"
    )
    _write_json(
        feature_manifest,
        {
            "status": "PASS",
            "failure_count": 0,
            "feature_count": 1,
            "output_root": "data/feature_matrices",
            "resolved_profile": "tier_1_research",
            "markets": ["ES"],
            "years": [2024],
            "feature_audit_gate": {"status": "PASS", "failure_count": 0, "failures": []},
            "registry": {
                "feature_cols": ["feature_signal"],
                "target_cols": ["target_ret_15m", *extra_targets],
            },
            "output_hashes": {}
            if v2_evidence
            else {"data/feature_matrices/ES/2024.parquet": file_sha256(feature_file)},
        },
    )

    universe = repo_root / "reports/data_audit/universe.json"
    _write_json(
        universe,
        {
            "status": "PASS",
            "summary": {"audit_status_counts": {"usable": 1}},
            "market_years": [
                {
                    "market": "ES",
                    "year": 2024,
                    "audit_status": "usable",
                    "usable_for_wfa": True,
                    "final_decision": "fixture",
                    "reason": "usable",
                }
            ],
        },
    )

    split_plan = repo_root / "reports/wfa/split/split_plan.json"
    split_payload = {
        "profile": profile,
        "resolved_profile": "tier_1_research",
        "input_root": "data/feature_matrices",
        "reports_root": "reports/wfa/split",
        "markets": ["ES"],
        "years": [2024],
        "config_hash": profile_config_hash([profile_config, models_config]),
        "script_hash": "fixture",
        "input_file_hashes": {
            "data/feature_matrices/ES/2024.parquet": file_sha256(feature_file)
        },
        "failure_count": 0,
        "fold_count": 1,
        "feature_manifest_gate": {
            "status": "PASS",
            "manifest_path": "reports/data_audit/current_state/tier1_core_phase4/active_feature_manifest.json",
            "manifest_hash": file_sha256(feature_manifest),
            "expected_output_root": "data/feature_matrices",
            "expected_resolved_profile": "tier_1_research",
        },
        "data_audit_universe": {
            "path": "reports/data_audit/universe.json",
            "file_hash": file_sha256(universe),
            "status_counts": {"usable": 1},
            "requires_usable_for_wfa": True,
        },
        "folds": [{"fold_id": "ES_research_0001", "market": "ES"}],
    }
    _write_json(split_plan, split_payload)

    split_acceptance = repo_root / "reports/wfa/split/split_plan_acceptance_report.json"
    _write_json(
        split_acceptance,
        {
            "status": "PASS_PHASE5_SPLIT_PLAN_ACCEPTED_REPORT_ONLY",
            "input_evidence": {"split_plan_json_sha256": file_sha256(split_plan)},
        },
    )

    paths = {
        "repo_root": repo_root,
        "feature_root": feature_root,
        "feature_manifest": feature_manifest,
        "split_plan": split_plan,
        "split_acceptance": split_acceptance,
        "profile_config": profile_config,
        "models_config": models_config,
        "report_root": repo_root / "reports/wfa/phase6_preflight",
    }
    if v2_evidence:
        label_file = repo_root / "data/labeled/ES/2024.parquet"
        _write_parquet(label_file, include_target=include_target, extra_targets=extra_targets)
        feature_placement_hashes = (
            repo_root / "reports/features_baseline/v2/post_active_feature_hashes.json"
        )
        _write_json(
            feature_placement_hashes,
            {
                "status": "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM",
                "scope": {
                    "markets": ["ES"],
                    "years": [2024],
                    "parquet_count": 1,
                    "sidecar_count": 0,
                },
                "records": [
                    {
                        "path": "data/feature_matrices/ES/2024.parquet",
                        "sha256": file_sha256(feature_file),
                        "staged_sha256": file_sha256(feature_file),
                        "active_matches_staged": True,
                        "backup_matches_pre_active": True,
                        "rows": 1,
                        "columns": len(pq.read_schema(feature_file).names),
                    }
                ],
            },
        )
        label_placement_hashes = repo_root / "reports/labels/v2/post_replacement_hashes.json"
        _write_json(
            label_placement_hashes,
            {
                "status": "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM",
                "label_semantics_id": V2_LABEL_SEMANTICS_ID,
                "scope": {"markets": ["ES"], "years": [2024], "file_count": 1},
                "records": [
                    {
                        "active_path": "data/labeled/ES/2024.parquet",
                        "active_sha256": file_sha256(label_file),
                        "staged_sha256": file_sha256(label_file),
                        "active_matches_staged": True,
                        "backup_matches_pre_active": True,
                        "active_rows": 1,
                    }
                ],
            },
        )
        paths["feature_placement_hashes"] = feature_placement_hashes
        paths["label_placement_hashes"] = label_placement_hashes
    return paths


def _run_preflight(paths: dict[str, Path], extra_args: list[str] | None = None) -> int:
    args = [
        "--repo-root",
        str(paths["repo_root"]),
        "--split-plan",
        str(paths["split_plan"]),
        "--split-acceptance",
        str(paths["split_acceptance"]),
        "--feature-root",
        str(paths["feature_root"]),
        "--feature-manifest",
        str(paths["feature_manifest"]),
        "--report-root",
        str(paths["report_root"]),
        "--profile-config",
        str(paths["profile_config"]),
        "--models-config",
        str(paths["models_config"]),
        "--predictions-root",
        str(paths["repo_root"] / "data/predictions"),
        "--expected-markets",
        "ES",
        "--expected-years",
        "2024",
    ]
    args.extend(extra_args or [])
    return main(args)


def _v2_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--feature-placement-hashes",
        str(paths["feature_placement_hashes"]),
        "--label-placement-hashes",
        str(paths["label_placement_hashes"]),
        "--expected-profile",
        "tier_1",
        "--expected-prediction-run",
        "phase6_v2_apex_30m60m_20260709_tier1_core",
    ]


def _write_hardened_acceptance(paths: dict[str, Path]) -> None:
    _write_json(
        paths["split_acceptance"],
        {
            "status": HARDENED_SPLIT_ACCEPTANCE_STATUS,
            "input_evidence": {
                "split_plan": paths["split_plan"].relative_to(paths["repo_root"]).as_posix(),
                "split_plan_sha256": file_sha256(paths["split_plan"]),
            },
            "summary": {
                "failure_count": 0,
                "fold_count": 1,
                "independent_test_claim_allowed": True,
                "modeling_allowed": False,
                "phase8_refresh_allowed": False,
                "prediction_materialization_allowed": False,
            },
        },
    )


def _make_hardened_split(paths: dict[str, Path]) -> None:
    payload = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    payload.update(
        {
            "status": HARDENED_SPLIT_STATUS,
            "profile": "tier_1",
            "config_hash": "hardened-fixture-config-hash",
            "fold_count": 1,
            "fold_count_by_market": {"ES": 1},
            "modeling_allowed": False,
            "prediction_materialization_allowed": False,
            "folds": [
                {
                    "fold_id": "ES_hardened_0001",
                    "market": "ES",
                    "train_start": "2023-01-01T00:00:00Z",
                    "train_end": "2023-12-29T23:59:00Z",
                    "validation_start": "2024-01-02T00:00:00Z",
                    "validation_end": "2024-06-28T23:59:00Z",
                    "validation_embargo_end": "2024-06-29T01:00:00Z",
                    "test_start": "2024-07-01T00:00:00Z",
                    "test_end": "2024-12-31T23:59:00Z",
                    "test_embargo_end": "2025-01-01T01:00:00Z",
                    "selection_source": "validation_only",
                    "independent_test_claim_allowed": True,
                    "final_holdout": False,
                }
            ],
        }
    )
    _write_json(paths["split_plan"], payload)
    _write_hardened_acceptance(paths)


def test_phase6_preflight_passes_without_training_or_predictions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path)

    assert _run_preflight(paths) == 0

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == PASS_STATUS
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["model_training_performed"] is False
    assert report["summary"]["prediction_generation_performed"] is False
    assert report["summary"]["prediction_file_count"] == 0
    assert (paths["report_root"] / "tier1_core_active_feature_set.json").is_file()


def test_phase6_preflight_fails_when_active_matrix_schema_lacks_model_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, include_target=False)

    assert _run_preflight(paths) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any(
        "active_feature_matrix_schemas_cover_phase6_required_columns" in failure
        for failure in report["failures"]
    )


def test_v2_preflight_passes_with_historical_prediction_artifacts_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    old_prediction = (
        paths["repo_root"]
        / "data/predictions/tier1_core_phase6_full_predictions_20260706/oos_predictions.parquet"
    )
    old_prediction.parent.mkdir(parents=True, exist_ok=True)
    old_prediction.write_bytes(b"historical")

    assert _run_preflight(paths, _v2_args(paths)) == 0

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == PASS_STATUS
    assert report["summary"]["prediction_file_count"] == 0
    assert report["summary"]["total_prediction_file_count"] == 1
    assert "--write-predictions" in report["candidate_phase6_command_not_approved"]


def test_v2_preflight_fails_when_feature_placement_hash_is_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    payload = json.loads(paths["feature_placement_hashes"].read_text(encoding="utf-8"))
    payload["records"][0]["sha256"] = "0" * 64
    _write_json(paths["feature_placement_hashes"], payload)

    assert _run_preflight(paths, _v2_args(paths)) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any("active_feature_files_match_split_and_manifest_hashes" in failure for failure in report["failures"])


def test_v2_preflight_fails_when_required_apex_target_column_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(
        tmp_path,
        v2_evidence=True,
        include_v2_targets=False,
        profile="tier_1",
    )

    assert _run_preflight(paths, _v2_args(paths)) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any(
        "active_v2_target_registry_and_schemas_cover_apex_30m60m_columns" in failure
        for failure in report["failures"]
    )


def test_v2_preflight_fails_when_split_acceptance_hash_is_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    payload = json.loads(paths["split_acceptance"].read_text(encoding="utf-8"))
    payload["input_evidence"]["split_plan_json_sha256"] = "0" * 64
    _write_json(paths["split_acceptance"], payload)

    assert _run_preflight(paths, _v2_args(paths)) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any("accepted_split_plan_bound_to_phase6_scope" in failure for failure in report["failures"])


def test_v2_preflight_accepts_hardened_split_acceptance_without_runner_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    _make_hardened_split(paths)

    assert _run_preflight(paths, _v2_args(paths)) == 0

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    checks = {check["name"]: check for check in report["checks"]}
    assert report["status"] == PASS_STATUS
    assert report["summary"]["commands_executed"] == 0
    assert checks["accepted_split_plan_bound_to_phase6_scope"]["evidence"][
        "split_acceptance_binding"
    ]["acceptance_kind"] == "hardened_train_validation_test"
    assert checks["hardened_split_validation_test_metadata"]["status"] == "PASS"


def test_v2_preflight_rejects_hardened_split_missing_validation_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    _make_hardened_split(paths)
    payload = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    del payload["folds"][0]["validation_start"]
    _write_json(paths["split_plan"], payload)
    _write_hardened_acceptance(paths)

    assert _run_preflight(paths, _v2_args(paths)) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any("hardened_split_validation_test_metadata" in failure for failure in report["failures"])


def test_v2_preflight_fails_on_scoped_candidate_prediction_collision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    paths = _fixture(tmp_path, v2_evidence=True, profile="tier_1")
    candidate_prediction = (
        paths["repo_root"]
        / "data/predictions/phase6_v2_apex_30m60m_20260709_tier1_core/oos_predictions.parquet"
    )
    candidate_prediction.parent.mkdir(parents=True, exist_ok=True)
    candidate_prediction.write_bytes(b"candidate")

    assert _run_preflight(paths, _v2_args(paths)) == 1

    report = json.loads(
        (paths["report_root"] / "wfa_runner_preflight_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == FAIL_STATUS
    assert any("generated_artifact_scope_and_no_prediction_writes" in failure for failure in report["failures"])
