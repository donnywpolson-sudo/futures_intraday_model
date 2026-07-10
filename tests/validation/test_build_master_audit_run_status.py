from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_master_audit_run_status as audit


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _base_repo(tmp_path: Path) -> Path:
    for name in ("MASTER_AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"):
        _write_text(tmp_path / name)
    _write_text(tmp_path / "configs" / "models.yaml", "purge:\n  resolved_purge_bars: 61\n")
    _write_json(tmp_path / "data" / "feature_matrices" / "feature_cols.json", ["feature_a"])
    _write_json(tmp_path / "data" / "feature_matrices" / "target_cols.json", ["target_a"])
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["target_timing"],
        {
            "status": "PASS_TARGET_TIMING_AUDIT",
            "stage": "target_timing_v2_tier1_core",
            "summary": {
                "failure_count": 0,
                "warning_count": 1,
                "pair_count": 8,
                "row_count": 100,
            },
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["feature_manifest"],
        {
            "status": "PASS",
            "failure_count": 0,
            "warning_count": 0,
            "feature_count": 114,
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["feature_leakage"],
        {
            "status": "PASS",
            "verdict": "PASS_NO_FEATURE_LEAKAGE_FOUND_UNDER_COMPLETED_BAR_CONVENTION",
            "summary_counts": {"matrix_file_status_counts": {"PASS": 8}},
            "source_evidence": {"feature_cols_sha256": "abc"},
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["split_plan"],
        {
            "fold_count": 48,
            "failure_count": 0,
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["wfa_split_contamination"],
        {
            "status": "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD",
            "summary": {
                "classification": "same_fold_rolling_retraining_research_only",
                "failure_count": 0,
                "warning_count": 2,
                "model_trust_ready": False,
                "valid_for_independent_holdout_claims": False,
            },
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["phase8_decision"],
        {
            "promoted": False,
            "research_alpha_ready": False,
            "model_promotion_allowed": False,
            "promotion_gate": {"promotion_blocker_count": 30},
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["statistical_validity"],
        {"status": "FAIL", "failure_count": 2, "warning_count": 0},
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["failure_analysis"],
        {"status": "PASS_REPORT_WRITTEN", "failure_count": 0, "warning_count": 0},
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["alpha_gap_matrix"],
        {
            "status": "PASS_REPORT_WRITTEN",
            "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
            "alpha_evidence_ready": False,
            "blockers": ["baseline_no_trade"],
            "bucket_status_counts": {"FAIL": 1},
            "source_evidence": {},
        },
    )
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["alpha_completion_closeout"],
        {
            "status": "PASS_REPORT_WRITTEN",
            "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
            "future_modeling_allowed": False,
            "promotion_allowed": False,
            "modeling_pause_required": True,
            "terminal_fail_count": 5,
            "missing_required_evidence_count": 11,
        },
    )
    return tmp_path


def _report(tmp_path: Path, *, git_status_lines: list[str] | None = None) -> dict[str, object]:
    return audit.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / audit.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=git_status_lines or [],
    )


def _row(report: dict[str, object], audit_area: str) -> dict[str, object]:
    rows = report["run_status_table"]
    assert isinstance(rows, list)
    return next(item for item in rows if item["audit_area"] == audit_area)


def test_inventory_classifies_existing_limited_evidence_without_phase_execution(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = _report(tmp_path)

    assert report["status"] == audit.PASS_STATUS
    assert report["summary"]["phase_audits_executed"] is False
    assert report["summary"]["data_model_commands_executed"] is False
    assert _row(report, "Phase 3")["detail_status"] == "RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE"
    assert _row(report, "Phase 5")["detail_status"] == "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD"
    assert _row(report, "Phase 8")["detail_status"] == "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE"
    assert _row(report, "Phase 10")["run_status"] == "N/A"
    assert _row(report, "Production / Paper / Live")["run_status"] == "N/A"


def test_missing_required_coordination_file_fails_inventory(tmp_path: Path) -> None:
    _base_repo(tmp_path)
    (tmp_path / "MASTER_AUDIT.md").unlink()

    report = _report(tmp_path)

    assert report["status"] == audit.FAIL_STATUS
    assert any("MASTER_AUDIT.md" in failure for failure in report["failures"])


def test_dirty_status_marks_evidence_unknown_not_stale_pass(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = _report(tmp_path, git_status_lines=[" M configs/models.yaml"])

    phase5 = _row(report, "Phase 5")
    models_evidence = next(
        item for item in phase5["accepted_evidence"] if item["path"] == "configs/models.yaml"
    )
    assert models_evidence["state"] == "unknown"
    assert models_evidence["git_status"] == "M"
    assert report["status"] == audit.PASS_STATUS


def test_source_hash_mismatch_is_reported_but_inventory_still_passes(tmp_path: Path) -> None:
    _base_repo(tmp_path)
    models_path = tmp_path / "configs" / "models.yaml"
    expected_hash = "0" * 64
    _write_json(
        tmp_path / audit.EVIDENCE_PATHS["alpha_gap_matrix"],
        {
            "status": "PASS_REPORT_WRITTEN",
            "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
            "alpha_evidence_ready": False,
            "blockers": ["baseline_no_trade"],
            "bucket_status_counts": {"FAIL": 1},
            "source_evidence": {
                "models_config": {
                    "path": "configs/models.yaml",
                    "sha256": expected_hash,
                }
            },
        },
    )
    assert audit.sha256_file(models_path) != expected_hash

    report = _report(tmp_path)

    assert report["status"] == audit.PASS_STATUS
    assert report["summary"]["stale_or_unknown_source_hash_mismatch_count"] == 1
    assert report["stale_or_unknown_source_hash_mismatches"][0]["path"] == "configs/models.yaml"


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    _base_repo(tmp_path)
    reports_root = tmp_path / audit.DEFAULT_REPORTS_ROOT

    exit_code = audit.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [audit.REPORT_JSON, audit.REPORT_MD]
    payload = json.loads((reports_root / audit.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["phase_audits_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad_output",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == audit.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
