from __future__ import annotations

import json
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation.build_phase7_hardened_prediction_audit_decision import (
    BLOCKED_STATUS,
    FAIL_STATUS,
    REPORT_JSON,
    REPORT_MD,
    DEFAULT_HARDENED_RUN,
    DEFAULT_REPORT_ONLY_RUN,
    V2_LABEL_SEMANTICS_ID,
    build_report,
    write_report,
)


MARKETS = ("6E", "CL", "ES", "ZN")
YEARS = (2023, 2024)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "prediction_count": 4_394_288,
        "prediction_markets": list(MARKETS),
        "prediction_path": None,
        "prediction_writes_enabled": False,
        "prediction_years": [2024],
        "predictions_root": None,
        "split_plan_hash": file_sha256(split_plan),
        "split_plan_path": split_plan.relative_to(repo_root).as_posix(),
        "unfiltered_selectable_fold_count": 4,
        "warning_count": 0,
        "years": list(YEARS),
    }


def _fixture(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path
    split_plan = repo_root / "reports/wfa/hardened/split_plan.json"
    split_acceptance = repo_root / "reports/wfa/hardened/hardened_split_acceptance_report.json"
    runner_preflight = repo_root / "reports/wfa/preflight/wfa_runner_preflight_report.json"
    feature_hashes = repo_root / "reports/features/post_active_feature_hashes.json"
    label_hashes = repo_root / "reports/labels/post_replacement_hashes.json"
    master_run_status = repo_root / "reports/master_audit/run_status.json"
    master_overview = repo_root / "reports/master_audit/overview.json"
    wfa_report = repo_root / "reports/wfa/hardened_report_only/wfa_report.json"
    predictions_manifest = repo_root / "reports/wfa/hardened_report_only/predictions_manifest.json"
    reports_root = repo_root / "reports/prediction_audit/hardened_decision"
    predictions_root = repo_root / "data/predictions"

    folds = [
        {
            "final_holdout": False,
            "fold_id": f"{market}_hardened_0001",
            "independent_test_claim_allowed": True,
            "is_final_holdout": False,
            "market": market,
            "selection_source": "validation_only",
            "split_group": "hardened_research",
            "test_selection_allowed": False,
        }
        for market in MARKETS
    ]
    _write_json(
        split_plan,
        {
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
                "split_plan": split_plan.relative_to(repo_root).as_posix(),
                "split_plan_sha256": file_sha256(split_plan),
            },
            "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_ACCEPTED_NO_MODELING",
            "summary": {
                "failure_count": 0,
                "fold_count": 4,
                "modeling_allowed": False,
                "prediction_materialization_allowed": False,
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

    base_payload = _base_wfa_payload(split_plan, repo_root)
    _write_json(wfa_report, base_payload)
    _write_json(predictions_manifest, base_payload)
    return {
        "repo_root": repo_root,
        "wfa_report": wfa_report,
        "predictions_manifest": predictions_manifest,
        "split_plan": split_plan,
        "split_acceptance": split_acceptance,
        "runner_preflight": runner_preflight,
        "feature_hashes": feature_hashes,
        "label_hashes": label_hashes,
        "master_run_status": master_run_status,
        "master_overview": master_overview,
        "reports_root": reports_root,
        "predictions_root": predictions_root,
    }


def _report(paths: dict[str, Path]) -> dict:
    return build_report(
        repo_root=paths["repo_root"],
        wfa_report_path=paths["wfa_report"],
        predictions_manifest_path=paths["predictions_manifest"],
        split_plan_path=paths["split_plan"],
        split_acceptance_path=paths["split_acceptance"],
        runner_preflight_path=paths["runner_preflight"],
        feature_hashes_path=paths["feature_hashes"],
        label_hashes_path=paths["label_hashes"],
        master_run_status_path=paths["master_run_status"],
        master_overview_path=paths["master_overview"],
        reports_root=paths["reports_root"],
        predictions_root=paths["predictions_root"],
        hardened_run=DEFAULT_HARDENED_RUN,
        report_only_run=DEFAULT_REPORT_ONLY_RUN,
        markets=MARKETS,
        years=YEARS,
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_blocks_phase7_when_prediction_parquet_is_absent(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = _report(paths)
    write_report(report, paths["reports_root"])

    assert report["status"] == BLOCKED_STATUS
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["normal_phase7_prediction_audit_allowed"] is False
    assert report["decision"]["phase7_audit_command"] is None
    assert (paths["reports_root"] / REPORT_JSON).exists()
    assert (paths["reports_root"] / REPORT_MD).exists()


def test_rejects_manifest_that_claims_predictions_were_written(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    manifest = json.loads(paths["predictions_manifest"].read_text(encoding="utf-8"))
    manifest["prediction_artifact_written"] = True
    _write_json(paths["predictions_manifest"], manifest)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert "prediction_artifact_written" in " ".join(report["failures"])


def test_rejects_existing_scoped_prediction_root(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    prediction_path = (
        paths["predictions_root"] / DEFAULT_REPORT_ONLY_RUN / "oos_predictions.parquet"
    )
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_bytes(b"not a real parquet")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert "scoped hardened prediction roots exist" in " ".join(report["failures"])


def test_rejects_scope_expansion(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    split_plan = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    split_plan["markets"] = [*MARKETS, "NQ"]
    _write_json(paths["split_plan"], split_plan)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert "split_plan markets mismatch" in " ".join(report["failures"])


def test_rejects_stale_manifest_split_hash(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    manifest = json.loads(paths["predictions_manifest"].read_text(encoding="utf-8"))
    manifest["split_plan_hash"] = "stale"
    _write_json(paths["predictions_manifest"], manifest)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert "split_plan_hash mismatch" in " ".join(report["failures"])


def test_rejects_unexpected_existing_report_file(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["reports_root"].mkdir(parents=True, exist_ok=True)
    (paths["reports_root"] / "unexpected.json").write_text("{}", encoding="utf-8")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert "unexpected report files" in " ".join(report["failures"])
