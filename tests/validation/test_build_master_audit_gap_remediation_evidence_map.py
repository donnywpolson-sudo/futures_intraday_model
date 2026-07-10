from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_master_audit_gap_remediation_evidence_map as gap


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_sources(repo_root: Path) -> None:
    payloads = {
        "phase1a_reconciliation": {
            "status": "PASS_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY",
            "summary": {
                "phase1a_source_lineage_ready": True,
                "archive_coverage_status": "PASS",
                "expected_archive_count": 2108,
                "missing_archive_count": 0,
                "missing_manifest_count": 0,
                "invalid_manifest_count": 0,
                "registry_validation_failure_count": 0,
                "original_delivery_reproducibility_ready": False,
                "model_trust_ready": False,
                "promotion_allowed": False,
            },
        },
        "master_readiness": {
            "status": "PASS_MASTER_AUDIT_RESEARCH_FACTORY_READINESS_REPORT_ONLY",
            "summary": {
                "readiness_score": 20,
                "model_trust_ready": False,
                "paper_live_ready": False,
                "promotion_allowed": False,
            },
            "research_readiness": {
                "scores": {
                    "data_integrity": 0,
                    "statistical_validity": 0,
                    "operational_resilience": 0,
                }
            },
        },
        "run_status": {
            "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
            "summary": {
                "current_line_classification": "closed_no_alpha_evidence",
                "current_split_classification": "same_fold_rolling_retraining_research_only",
            },
        },
        "phase1b_reconciliation": {
            "status": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
            "summary": {
                "broad_phase1b_accepted": False,
                "broad_phase1b_alignment_status": "FAIL",
                "phase1b_limited_scope_ready": True,
                "raw_dbn_alignment_audit_executed": False,
            },
        },
        "phase1b_broad_reconciliation": {
            "status": "PASS_MASTER_AUDIT_PHASE1B_BROAD_RECONCILIATION_REPORT_ONLY",
            "summary": {
                "raw_row_parity_and_conversion_ready": True,
                "broad_phase1b_accepted": True,
                "market_report_count": 33,
                "pass_market_reports": 33,
                "fail_market_reports": 0,
                "missing_report_count": 0,
                "expected_market_year_count": 527,
                "raw_market_year_count": 527,
                "needs_phase1b_conversion_count": 0,
                "raw_only_count": 0,
                "invalid_manifest_count": 0,
                "source_hash_mismatch_count": 0,
                "definition_join_mismatch_count": 0,
                "raw_schema_failure_count": 0,
                "required_schema_exception_failure_count": 0,
                "accepted_repair_source_count": 6,
                "legacy_full_alignment_context": (
                    "SUPERSEDED_BY_CORRECTED_EXPECTED_ONLY_BATCHES"
                ),
                "raw_dbn_alignment_audit_executed": False,
                "phase1b_conversion_executed": False,
                "phase2_accepted": False,
                "model_trust_ready": False,
                "promotion_allowed": False,
            },
        },
        "phase2_reconciliation": {
            "status": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
            "summary": {
                "phase2_full_master_audit_accepted": False,
                "phase2_limited_active_hash_lineage_ready": True,
                "phase2_session_normalization_audit_accepted": False,
                "readiness_status": "WARN",
            },
        },
        "phase2_active_scope_reconciliation": {
            "status": "PASS_MASTER_AUDIT_PHASE2_ACTIVE_SCOPE_RECONCILIATION_REPORT_ONLY",
            "summary": {
                "causal_session_active_scope_ready": True,
                "phase2_active_scope_ready": True,
                "active_scoped_output_count": 8,
                "active_hash_match_count": 8,
                "phase2_full_master_audit_accepted": False,
                "phase2_session_normalization_audit_accepted": False,
                "phase2_build_or_readiness_accepted": False,
                "audit_phase2_causal_session_normalization_executed": False,
                "phase2_readiness_or_build_executed": False,
                "causal_rebuild_executed": False,
                "parquet_audit_executed": False,
                "causal_parquet_read_executed": False,
                "readiness_status": "WARN",
                "readiness_severe_blocker_count": 0,
                "scoped_raw_without_causal_count": 0,
                "target_timing_status": "PASS_TARGET_TIMING_AUDIT",
                "target_timing_pair_count": 8,
                "target_timing_row_count": 2_837_374,
                "target_timing_row_key_mismatches": 0,
                "target_timing_entry_30m_not_after_ts": 0,
                "target_timing_entry_60m_not_after_ts": 0,
                "target_timing_exit_30m_offset_mismatches": 0,
                "target_timing_exit_60m_offset_mismatches": 0,
                "target_timing_same_session_30m_violations": 0,
                "target_timing_same_session_60m_violations": 0,
                "completed_bar_convention_assumed": True,
                "model_trust_ready": False,
                "promotion_allowed": False,
                "paper_live_allowed": False,
                "production_ready": False,
            },
        },
        "target_timing": {
            "status": "PASS_TARGET_TIMING_AUDIT",
            "summary": {
                "failure_count": 0,
                "warning_count": 1,
            },
        },
        "statistical_validity": {
            "status": "FAIL",
            "statistical_validity_ready": False,
            "failure_count": 6,
        },
        "alpha_gap_matrix": {
            "status": "FAIL",
            "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
            "alpha_evidence_ready": False,
        },
        "alpha_completion_closeout": {
            "status": "PASS",
            "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
            "future_evidence_work_allowed": True,
            "future_modeling_allowed": False,
            "promotion_allowed": False,
        },
        "execution_realism": {
            "status": "FAIL",
            "execution_realism_gate": {
                "status": "FAIL",
                "execution_realism_ready": False,
                "failure_count": 4,
            },
        },
    }
    for key, path in gap.SOURCE_PATHS.items():
        if path.suffix == ".json":
            _write_json(repo_root / path, payloads[key])
        else:
            _write_text(repo_root / path, f"{key} evidence\n")


def test_gap_map_is_report_only_and_fail_closed(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    report = gap.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / gap.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == gap.PASS_STATUS
    assert report["summary"]["gap_area_statuses"] == {
        "data_integrity": "PASS",
        "statistical_validity": "FAIL",
        "operational_resilience": "FAIL",
    }
    assert report["summary"]["any_gap_area_pass"] is True
    assert report["summary"]["data_integrity_ready"] is True
    assert report["summary"]["promotion_allowed"] is False
    assert all(value is False for value in report["non_approval"].values())
    data_checks = {
        check["check_id"]: check for check in report["gap_maps"]["data_integrity"]["checks"]
    }
    assert data_checks["source_acquisition_lineage"]["status"] == "PASS"
    assert data_checks["source_acquisition_lineage"]["review_status"] == "PASS"
    assert data_checks["raw_row_parity_and_conversion"]["status"] == "PASS"
    assert data_checks["raw_row_parity_and_conversion"]["review_status"] == "PASS"
    assert data_checks["causal_session_active_scope"]["status"] == "PASS"
    assert data_checks["causal_session_active_scope"]["review_status"] == "PASS"
    for gap_map in report["gap_maps"].values():
        assert gap_map["score_eligible"] is False
        assert gap_map["score_contribution"] == 0
        for check in gap_map["checks"]:
            assert check["source_hashes"]
            if check["check_id"] not in {
                "source_acquisition_lineage",
                "raw_row_parity_and_conversion",
                "causal_session_active_scope",
            }:
                assert check["status"] == "FAIL"
                assert check["review_status"] == "FAIL"


def test_missing_source_file_stays_missing_evidence_not_pass(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    (tmp_path / gap.SOURCE_PATHS["execution_realism"]).unlink()

    report = gap.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / gap.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    operational = report["gap_maps"]["operational_resilience"]
    assert operational["status"] == "MISSING_EVIDENCE"
    assert operational["score_eligible"] is False
    assert any(check["status"] == "MISSING_EVIDENCE" for check in operational["checks"])
    assert report["summary"]["model_trust_ready"] is False


def test_main_writes_exact_json_and_markdown_pair(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    reports_root = tmp_path / gap.DEFAULT_REPORTS_ROOT

    exit_code = gap.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        gap.REPORT_JSON,
        gap.REPORT_MD,
    ]
    payload = json.loads((reports_root / gap.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["gap_area_statuses"]["data_integrity"] == "PASS"
    assert payload["summary"]["model_trust_ready"] is False


def test_phase2_active_failure_keeps_data_integrity_failed(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    path = tmp_path / gap.SOURCE_PATHS["phase2_active_scope_reconciliation"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["target_timing_row_key_mismatches"] = 1
    _write_json(path, payload)

    report = gap.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / gap.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    data_integrity = report["gap_maps"]["data_integrity"]
    checks = {check["check_id"]: check for check in data_integrity["checks"]}
    assert checks["source_acquisition_lineage"]["status"] == "PASS"
    assert checks["raw_row_parity_and_conversion"]["status"] == "PASS"
    assert checks["causal_session_active_scope"]["status"] == "FAIL"
    assert data_integrity["status"] == "FAIL"
    assert data_integrity["ready"] is False
    assert report["summary"]["data_integrity_ready"] is False
    assert report["summary"]["model_trust_ready"] is False


def test_phase1b_broad_failure_keeps_raw_row_parity_failed(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    path = tmp_path / gap.SOURCE_PATHS["phase1b_broad_reconciliation"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["source_hash_mismatch_count"] = 1
    _write_json(path, payload)

    report = gap.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / gap.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    checks = {
        check["check_id"]: check
        for check in report["gap_maps"]["data_integrity"]["checks"]
    }
    assert checks["source_acquisition_lineage"]["status"] == "PASS"
    assert checks["raw_row_parity_and_conversion"]["status"] == "FAIL"
    assert checks["causal_session_active_scope"]["status"] == "PASS"
    assert report["summary"]["data_integrity_ready"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    report = gap.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == gap.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
