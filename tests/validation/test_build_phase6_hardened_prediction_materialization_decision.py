from __future__ import annotations

import json
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation.build_phase6_hardened_prediction_materialization_decision import (
    BLOCKED_STATUS,
    FAIL_STATUS,
    REPORT_JSON,
    REPORT_MD,
    build_report,
    write_report,
)
from scripts.validation.build_phase7_hardened_prediction_audit_decision import (
    DEFAULT_HARDENED_RUN,
    DEFAULT_REPORT_ONLY_RUN,
    EXPECTED_PREDICTION_COUNT,
    V2_LABEL_SEMANTICS_ID,
)


MARKETS = ("6E", "CL", "ES", "ZN")
YEARS = (2023, 2024)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _base_wfa_payload(split_plan: Path, repo_root: Path) -> dict:
    return {
        "artifact_evidence_ready": True,
        "duplicate_prediction_count": 0,
        "failure_count": 0,
        "fold_count": 4,
        "markets": list(MARKETS),
        "output_root": None,
        "prediction_artifact_write_skipped": True,
        "prediction_artifact_written": False,
        "prediction_count": EXPECTED_PREDICTION_COUNT,
        "prediction_markets": list(MARKETS),
        "prediction_path": None,
        "prediction_writes_enabled": False,
        "prediction_years": [2024],
        "predictions_root": None,
        "split_plan_hash": file_sha256(split_plan),
        "split_plan_path": _rel(split_plan, repo_root),
        "unfiltered_selectable_fold_count": 4,
        "warning_count": 0,
        "years": list(YEARS),
    }


def _fixture(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path
    phase7_decision = repo_root / "reports/prediction_audit/phase7/phase7_prediction_audit_decision.json"
    wfa_report = repo_root / "reports/wfa/report_only/wfa_report.json"
    predictions_manifest = repo_root / "reports/wfa/report_only/predictions_manifest.json"
    split_plan = repo_root / "reports/wfa/hardened/split_plan.json"
    split_acceptance = repo_root / "reports/wfa/hardened/hardened_split_acceptance_report.json"
    runner_preflight = repo_root / "reports/wfa/preflight/wfa_runner_preflight_report.json"
    feature_set = repo_root / "reports/wfa/preflight/tier1_core_active_feature_set.json"
    feature_hashes = repo_root / "reports/features/post_active_feature_hashes.json"
    label_hashes = repo_root / "reports/labels/post_replacement_hashes.json"
    data_audit_universe = repo_root / "reports/data_audit/universe.json"
    master_run_status = repo_root / "reports/master_audit/run_status.json"
    master_overview = repo_root / "reports/master_audit/overview.json"
    runner_script = repo_root / "scripts/phase7_wfa/run_wfa.py"
    models_config = repo_root / "configs/models.yaml"
    profile_config = repo_root / "configs/alpha_tiered.yaml"
    reports_root = repo_root / "reports/wfa/materialization_decision"
    predictions_root = repo_root / "data/predictions"
    hardened_reports_root = repo_root / "reports/wfa/phase6_hardened"

    _write_json(
        data_audit_universe,
        {
            "status": "PASS",
            "summary": {"audit_status_counts": {"usable": 8}},
            "market_years": [
                {
                    "market": market,
                    "year": year,
                    "audit_status": "usable",
                    "usable_for_wfa": True,
                    "final_decision": "ready_for_tier1_wfa_research_with_accepted_caveats",
                    "reason": "fixture",
                }
                for market in MARKETS
                for year in YEARS
            ],
        },
    )

    folds = [
        {
            "embargo_bars": 61,
            "final_holdout": False,
            "fold_id": f"{market}_hardened_0001",
            "independent_test_claim_allowed": True,
            "is_final_holdout": False,
            "market": market,
            "selection_allowed": True,
            "selection_source": "validation_only",
            "split_group": "hardened_research",
            "test_embargo_end": "2025-01-01T01:00:00Z",
            "test_end": "2024-12-31T23:59:00Z",
            "test_selection_allowed": False,
            "test_start": "2024-07-01T00:00:00Z",
            "train_end": "2023-12-29T23:59:00Z",
            "train_start": "2023-01-01T00:00:00Z",
            "validation_embargo_end": "2024-06-29T01:00:00Z",
            "validation_end": "2024-06-28T23:59:00Z",
            "validation_start": "2024-01-02T00:00:00Z",
        }
        for market in MARKETS
    ]
    _write_json(
        split_plan,
        {
            "data_audit_universe": {
                "path": _rel(data_audit_universe, repo_root),
                "file_hash": file_sha256(data_audit_universe),
            },
            "failure_count": 0,
            "fold_count": 4,
            "folds": folds,
            "markets": list(MARKETS),
            "modeling_allowed": False,
            "prediction_materialization_allowed": False,
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING",
            "years": list(YEARS),
        },
    )
    _write_json(
        split_acceptance,
        {
            "input_evidence": {
                "split_plan": _rel(split_plan, repo_root),
                "split_plan_sha256": file_sha256(split_plan),
            },
            "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_ACCEPTED_NO_MODELING",
            "summary": {
                "failure_count": 0,
                "fold_count": 4,
                "independent_test_claim_allowed": True,
                "modeling_allowed": False,
                "phase8_refresh_allowed": False,
                "prediction_materialization_allowed": False,
            },
        },
    )

    _write_json(wfa_report, _base_wfa_payload(split_plan, repo_root))
    _write_json(predictions_manifest, _base_wfa_payload(split_plan, repo_root))
    _write_json(
        phase7_decision,
        {
            "status": "BLOCKED_PHASE7_PREDICTION_ARTIFACT_AUDIT_NO_SAVED_PREDICTIONS",
            "summary": {
                "block_reason": "no_saved_oos_prediction_parquet",
                "failure_count": 0,
                "normal_phase7_prediction_audit_allowed": False,
            },
            "decision": {
                "phase7_audit_command": None,
                "future_unblock_requires_separate_prediction_materialization_approval": True,
            },
        },
    )
    _write_json(
        runner_preflight,
        {
            "status": "PASS_PHASE6_WFA_RUNNER_PREFLIGHT_READY_REPORT_ONLY",
            "summary": {
                "commands_executed": 0,
                "failure_count": 0,
                "feature_count": 114,
                "fold_count": 4,
                "model_training_performed": False,
                "prediction_file_count": 0,
                "prediction_generation_performed": False,
            },
        },
    )
    _write_json(
        feature_set,
        {
            "allowed_for_wfa": True,
            "evidence": {
                "feature_manifest_hash": "f" * 64,
                "feature_manifest_path": "reports/features/baseline_feature_manifest.json",
                "split_acceptance_hash": file_sha256(split_acceptance),
                "split_acceptance_path": _rel(split_acceptance, repo_root),
                "split_plan_hash": file_sha256(split_plan),
                "split_plan_path": _rel(split_plan, repo_root),
            },
            "feature_count": 114,
            "feature_root": "data/feature_matrices",
            "status": "FROZEN",
        },
    )
    _write_json(
        feature_hashes,
        {
            "records": [{"path": f"record_{idx}.parquet"} for idx in range(12)],
            "status": "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM",
        },
    )
    _write_json(
        label_hashes,
        {
            "label_semantics_id": V2_LABEL_SEMANTICS_ID,
            "records": [
                {"market": market, "year": year}
                for market in MARKETS
                for year in YEARS
            ],
            "status": "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM",
        },
    )
    phase_rows = [
        {"audit_area": "Phase 6", "run_status": "NOT_RUN"},
        {"audit_area": "Phase 7", "run_status": "NOT_RUN"},
    ]
    _write_json(
        master_run_status,
        {"status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY", "run_status_table": phase_rows},
    )
    _write_json(
        master_overview,
        {
            "overview_sections": {"phase_status_summary": phase_rows},
            "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
        },
    )
    _write_text(
        runner_script,
        "if hardened_split and (write_predictions or predictions_root is not None):\n"
        "    raise SystemExit('hardened split WFA is report-only only; --write-predictions and "
        "--predictions-root are forbidden')\n",
    )
    _write_text(models_config, "models: {}\n")
    _write_text(profile_config, "profiles: {}\n")

    return {
        "repo_root": repo_root,
        "phase7_decision": phase7_decision,
        "wfa_report": wfa_report,
        "predictions_manifest": predictions_manifest,
        "split_plan": split_plan,
        "split_acceptance": split_acceptance,
        "runner_preflight": runner_preflight,
        "feature_set": feature_set,
        "feature_hashes": feature_hashes,
        "label_hashes": label_hashes,
        "data_audit_universe": data_audit_universe,
        "master_run_status": master_run_status,
        "master_overview": master_overview,
        "runner_script": runner_script,
        "models_config": models_config,
        "profile_config": profile_config,
        "reports_root": reports_root,
        "predictions_root": predictions_root,
        "hardened_reports_root": hardened_reports_root,
        "input_root": repo_root / "data/feature_matrices",
    }


def _report(paths: dict[str, Path]) -> dict:
    return build_report(
        repo_root=paths["repo_root"],
        phase7_decision_path=paths["phase7_decision"],
        wfa_report_path=paths["wfa_report"],
        predictions_manifest_path=paths["predictions_manifest"],
        split_plan_path=paths["split_plan"],
        split_acceptance_path=paths["split_acceptance"],
        runner_preflight_path=paths["runner_preflight"],
        feature_set_path=paths["feature_set"],
        feature_hashes_path=paths["feature_hashes"],
        label_hashes_path=paths["label_hashes"],
        data_audit_universe_path=paths["data_audit_universe"],
        master_run_status_path=paths["master_run_status"],
        master_overview_path=paths["master_overview"],
        reports_root=paths["reports_root"],
        predictions_root=paths["predictions_root"],
        hardened_reports_root=paths["hardened_reports_root"],
        runner_script_path=paths["runner_script"],
        input_root=paths["input_root"],
        models_config_path=paths["models_config"],
        profile_config_path=paths["profile_config"],
        hardened_run=DEFAULT_HARDENED_RUN,
        report_only_run=DEFAULT_REPORT_ONLY_RUN,
        markets=MARKETS,
        years=YEARS,
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_blocks_materialization_under_current_runner_guard(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = _report(paths)
    write_report(report, paths["reports_root"])

    assert report["status"] == BLOCKED_STATUS
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["candidate_command_approved_for_execution"] is False
    assert report["summary"]["prediction_materialization_executed"] is False
    assert report["summary"]["future_runner_patch_required"] is True
    assert "scripts.phase6_wfa.run_wfa" in report["decision"]["candidate_write_predictions_command_not_approved"]
    assert "--write-predictions" in report["decision"]["candidate_write_predictions_command_not_approved"]
    assert (paths["reports_root"] / REPORT_JSON).exists()
    assert (paths["reports_root"] / REPORT_MD).exists()


def test_fails_when_runner_write_guard_is_missing(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_text(paths["runner_script"], "def main():\n    return 0\n")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("current_runner_forbids_hardened_prediction_writes" in failure for failure in report["failures"])


def test_fails_when_phase7_decision_is_not_blocked_on_absent_predictions(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["phase7_decision"].read_text(encoding="utf-8"))
    payload["status"] = "PASS_PHASE7_AUDIT_READY"
    _write_json(paths["phase7_decision"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("phase7_report_only_decision_blocks_on_absent_saved_predictions" in failure for failure in report["failures"])


def test_fails_when_future_prediction_output_already_exists(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    collision = paths["predictions_root"] / DEFAULT_HARDENED_RUN / "oos_predictions.parquet"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_bytes(b"stale")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("future_hardened_prediction_output_roots_are_absent" in failure for failure in report["failures"])


def test_fails_when_hardened_split_metadata_is_missing(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    del payload["folds"][0]["validation_start"]
    _write_json(paths["split_plan"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("hardened_split_validation_test_metadata" in failure for failure in report["failures"])


def test_fails_when_data_audit_universe_hash_is_stale(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    payload["data_audit_universe"]["file_hash"] = "0" * 64
    _write_json(paths["split_plan"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("data_audit_universe_exact_usable_scope" in failure for failure in report["failures"])


def test_fails_on_unexpected_existing_decision_report_file(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["reports_root"].mkdir(parents=True, exist_ok=True)
    (paths["reports_root"] / "extra.json").write_text("{}", encoding="utf-8")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("decision_report_root_contains_only_expected_files" in failure for failure in report["failures"])
