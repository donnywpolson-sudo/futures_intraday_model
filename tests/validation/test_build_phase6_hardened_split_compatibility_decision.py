import json
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation.build_phase6_hardened_split_compatibility_decision import (
    FAIL_STATUS,
    PASS_STATUS,
    REPORT_JSON,
    REPORT_MD,
    build_report,
    main,
)
from scripts.validation.review_phase6_wfa_runner_preflight import V2_LABEL_SEMANTICS_ID


MARKETS = ("6E", "CL", "ES", "ZN")
YEARS = (2023, 2024)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _fixture(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path
    feature_root = repo_root / "data/feature_matrices"
    label_root = repo_root / "data/labeled"
    split_input_hashes: dict[str, str] = {}
    feature_records: list[dict] = []
    label_records: list[dict] = []
    outputs: list[dict] = []

    for market in MARKETS:
        for year in YEARS:
            feature_path = feature_root / market / f"{year}.parquet"
            label_path = label_root / market / f"{year}.parquet"
            _write_bytes(feature_path, f"{market}-{year}-features".encode("ascii"))
            _write_bytes(label_path, f"{market}-{year}-labels".encode("ascii"))
            feature_hash = file_sha256(feature_path)
            label_hash = file_sha256(label_path)
            feature_rel = _rel(feature_path, repo_root)
            label_rel = _rel(label_path, repo_root)
            split_input_hashes[feature_rel] = feature_hash
            feature_records.append(
                {
                    "path": feature_rel,
                    "sha256": feature_hash,
                    "staged_sha256": feature_hash,
                    "active_matches_staged": True,
                }
            )
            label_records.append(
                {
                    "active_path": label_rel,
                    "active_sha256": label_hash,
                    "staged_sha256": label_hash,
                    "active_matches_staged": True,
                    "market": market,
                    "year": year,
                }
            )
            outputs.append(
                {
                    "market": market,
                    "year": year,
                    "status": "PASS",
                    "output_path": feature_rel,
                    "feature_count": 114,
                    "input_path": label_rel,
                }
            )

    feature_manifest = repo_root / "reports/features/baseline_feature_manifest.json"
    _write_json(
        feature_manifest,
        {
            "status": "PASS",
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "output_root": "data/feature_matrices",
            "feature_count": 114,
            "failure_count": 0,
            "warning_count": 0,
            "outputs": outputs,
        },
    )

    feature_hashes = repo_root / "reports/features/post_active_feature_hashes.json"
    _write_json(
        feature_hashes,
        {
            "status": "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM",
            "failures": [],
            "records": feature_records,
        },
    )
    label_hashes = repo_root / "reports/labels/post_replacement_hashes.json"
    _write_json(
        label_hashes,
        {
            "status": "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM",
            "label_semantics_id": V2_LABEL_SEMANTICS_ID,
            "failures": [],
            "records": label_records,
        },
    )

    folds = []
    for market in MARKETS:
        folds.append(
            {
                "fold_id": f"{market}_hardened_0001",
                "market": market,
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
        )
    split_plan = repo_root / "reports/wfa/hardened/split_plan.json"
    _write_json(
        split_plan,
        {
            "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING",
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "input_root": "data/feature_matrices",
            "markets": list(MARKETS),
            "years": list(YEARS),
            "fold_count": len(MARKETS),
            "fold_count_by_market": {market: 1 for market in MARKETS},
            "failure_count": 0,
            "modeling_allowed": False,
            "prediction_materialization_allowed": False,
            "input_file_hashes": split_input_hashes,
            "folds": folds,
        },
    )

    split_acceptance = repo_root / "reports/wfa/hardened/hardened_split_acceptance_report.json"
    _write_json(
        split_acceptance,
        {
            "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_ACCEPTED_NO_MODELING",
            "input_evidence": {
                "split_plan": _rel(split_plan, repo_root),
                "split_plan_sha256": file_sha256(split_plan),
            },
            "summary": {
                "failure_count": 0,
                "fold_count": len(MARKETS),
                "independent_test_claim_allowed": True,
                "modeling_allowed": False,
                "phase8_refresh_allowed": False,
                "prediction_materialization_allowed": False,
            },
        },
    )

    master_run_status = repo_root / "reports/master_audit/run_status.json"
    _write_json(
        master_run_status,
        {
            "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
            "failures": [],
            "run_status_table": [
                {
                    "audit_area": "Phase 6",
                    "detail_status": "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
                    "evidence_state": "unknown",
                    "run_status": "NOT_RUN",
                },
                {
                    "audit_area": "Phase 7",
                    "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                    "evidence_state": "missing",
                    "run_status": "NOT_RUN",
                },
            ],
        },
    )
    master_overview = repo_root / "reports/master_audit/overview.json"
    _write_json(
        master_overview,
        {
            "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
            "failures": [],
            "overview_sections": {
                "B_architecture_review": {
                    "phase_status_summary": [
                        {
                            "audit_area": "Phase 6",
                            "detail_status": "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
                            "evidence_state": "unknown",
                            "run_status": "NOT_RUN",
                        },
                        {
                            "audit_area": "Phase 7",
                            "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                            "evidence_state": "missing",
                            "run_status": "NOT_RUN",
                        },
                    ]
                }
            },
        },
    )

    return {
        "repo_root": repo_root,
        "split_plan": split_plan,
        "split_acceptance": split_acceptance,
        "feature_root": feature_root,
        "feature_manifest": feature_manifest,
        "feature_hashes": feature_hashes,
        "label_hashes": label_hashes,
        "master_run_status": master_run_status,
        "master_overview": master_overview,
        "reports_root": repo_root / "reports/wfa/compatibility",
        "predictions_root": repo_root / "data/predictions",
    }


def _report(paths: dict[str, Path]) -> dict:
    return build_report(
        repo_root=paths["repo_root"],
        split_plan_path=paths["split_plan"],
        split_acceptance_path=paths["split_acceptance"],
        feature_root=paths["feature_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_hashes_path=paths["feature_hashes"],
        label_hashes_path=paths["label_hashes"],
        master_audit_run_status_path=paths["master_run_status"],
        master_audit_overview_path=paths["master_overview"],
        reports_root=paths["reports_root"],
        predictions_root=paths["predictions_root"],
        expected_prediction_run="phase6_v2_apex_30m60m_20260709_tier1_core_hardened",
        markets=MARKETS,
        years=YEARS,
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_hardened_split_compatibility_passes_without_execution(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    report = _report(paths)

    assert report["status"] == PASS_STATUS
    assert report["summary"]["phase6_preflight_compatible"] is True
    assert report["summary"]["phase7_decision"] == "DEFER_PHASE7_NO_HARDENED_PREDICTIONS"
    assert report["summary"]["wfa_execution_allowed"] is False
    assert report["summary"]["prediction_materialization_allowed"] is False
    assert "--expected-profile tier_1" in report["candidate_phase6_preflight_command_not_approved"]
    assert "scripts.validation.review_phase6_wfa_runner_preflight" in report[
        "candidate_phase6_preflight_command_not_approved"
    ]
    assert {check["status"] for check in report["checks"]} == {"PASS"}


def test_hardened_split_compatibility_fails_on_stale_acceptance_path(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["split_acceptance"].read_text(encoding="utf-8"))
    payload["input_evidence"]["split_plan"] = "reports/wfa/wrong/split_plan.json"
    _write_json(paths["split_acceptance"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("hardened_split_acceptance_bound_to_split" in failure for failure in report["failures"])


def test_hardened_split_compatibility_fails_on_missing_validation_window(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["split_plan"].read_text(encoding="utf-8"))
    del payload["folds"][0]["validation_start"]
    _write_json(paths["split_plan"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("hardened_split_exact_scope_and_metadata" in failure for failure in report["failures"])


def test_hardened_split_compatibility_fails_on_label_hash_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    payload = json.loads(paths["label_hashes"].read_text(encoding="utf-8"))
    payload["records"][0]["active_sha256"] = "0" * 64
    _write_json(paths["label_hashes"], payload)

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert any("active_v2_label_feature_hashes_match_hardened_split" in failure for failure in report["failures"])


def test_hardened_split_compatibility_fails_on_scoped_prediction_collision(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    collision = (
        paths["predictions_root"]
        / "phase6_v2_apex_30m60m_20260709_tier1_core_hardened/oos_predictions.parquet"
    )
    _write_bytes(collision, b"stale predictions")

    report = _report(paths)

    assert report["status"] == FAIL_STATUS
    assert report["summary"]["phase7_decision"] == "BLOCKED_PREDICTION_COLLISION"
    assert any("no_hardened_phase6_predictions_exist_phase7_deferred" in failure for failure in report["failures"])


def test_hardened_split_compatibility_main_writes_only_decision_reports(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)

    result = main(
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
            "--feature-placement-hashes",
            str(paths["feature_hashes"]),
            "--label-placement-hashes",
            str(paths["label_hashes"]),
            "--master-audit-run-status",
            str(paths["master_run_status"]),
            "--master-audit-overview",
            str(paths["master_overview"]),
            "--reports-root",
            str(paths["reports_root"]),
            "--predictions-root",
            str(paths["predictions_root"]),
            "--markets",
            ",".join(MARKETS),
            "--years",
            ",".join(str(year) for year in YEARS),
        ]
    )

    assert result == 0
    assert sorted(path.name for path in paths["reports_root"].iterdir()) == [REPORT_JSON, REPORT_MD]
    report = json.loads((paths["reports_root"] / REPORT_JSON).read_text(encoding="utf-8"))
    assert report["status"] == PASS_STATUS
