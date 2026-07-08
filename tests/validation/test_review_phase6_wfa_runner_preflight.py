import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.pipeline_gates import file_sha256
from scripts.profile_scope import profile_config_hash
from scripts.validation.review_phase6_wfa_runner_preflight import (
    FAIL_STATUS,
    PASS_STATUS,
    main,
)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_parquet(path: Path, *, include_target: bool = True) -> None:
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
    pq.write_table(pa.table(payload), path)


def _fixture(tmp_path: Path, *, include_target: bool = True) -> dict[str, Path]:
    repo_root = tmp_path
    feature_root = repo_root / "data/feature_matrices"
    feature_file = feature_root / "ES/2024.parquet"
    _write_parquet(feature_file, include_target=include_target)
    _write_json(feature_root / "feature_cols.json", ["feature_signal"])
    _write_json(feature_root / "target_cols.json", ["target_ret_15m"])

    profile_config = repo_root / "configs/alpha_tiered.yaml"
    _write_text(
        profile_config,
        "aliases:\n"
        "  tier_1_core: tier_1_research\n"
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
                "target_cols": ["target_ret_15m"],
            },
            "output_hashes": {
                "data/feature_matrices/ES/2024.parquet": file_sha256(feature_file)
            },
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
        "profile": "tier_1_core",
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

    return {
        "repo_root": repo_root,
        "feature_root": feature_root,
        "feature_manifest": feature_manifest,
        "split_plan": split_plan,
        "split_acceptance": split_acceptance,
        "profile_config": profile_config,
        "models_config": models_config,
        "report_root": repo_root / "reports/wfa/phase6_preflight",
    }


def _run_preflight(paths: dict[str, Path]) -> int:
    return main(
        [
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
    )


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
