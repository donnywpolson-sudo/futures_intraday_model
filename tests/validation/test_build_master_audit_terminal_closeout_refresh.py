from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_master_audit_terminal_closeout_refresh as builder


TEST_INPUTS = {
    "statistical_closeout_boundary": Path("in/statistical_closeout_boundary.json"),
    "after_phase2_gap_map": Path("in/after_phase2_gap_map.json"),
    "master_audit_closeout": Path("in/master_audit_closeout.json"),
    "model_trust_audit": Path("in/model_trust_audit.json"),
    "alpha_closeout": Path("in/alpha_closeout.json"),
    "run_status": Path("in/run_status.json"),
    "adversarial_audit": Path("in/adversarial_audit.md"),
}


def _write_json(root: Path, rel_path: Path, payload: dict) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(root: Path, rel_path: Path, text: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _statistical_closeout_boundary() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_CLOSEOUT_BOUNDARY_DECISION_REPORT_ONLY",
        "summary": {
            "closeout_boundary_decision": builder.STATISTICAL_BOUNDARY_DECISION,
            "statistical_validity": "FAIL",
            "statistical_validity_ready": False,
            "master_audit_statistical_validity_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "gap_map_refresh_allowed": False,
            "statistical_validity_gap_upgrade_allowed": False,
        },
    }


def _after_phase2_gap_map() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY",
        "summary": {
            "gap_area_statuses": {
                "data_integrity": "PASS",
                "statistical_validity": "FAIL",
                "operational_resilience": "FAIL",
            },
            "data_integrity_ready": True,
            "statistical_validity_ready": False,
            "operational_resilience_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "paper_live_ready": False,
            "production_ready": False,
        },
    }


def _master_audit_closeout() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY",
        "summary": {
            "closeout_classification": "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY",
            "current_line_classification": "closed_no_alpha_evidence",
            "full_master_audit_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
        },
    }


def _model_trust_audit() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "permitted_use_label": "research_only",
        "non_approval": {
            "cleanup": False,
            "data_replacement": False,
            "live": False,
            "paper": False,
            "prediction_generation": False,
            "promotion": False,
            "provider_downloads": False,
            "staging_commit_push": False,
            "wfa_model_training": False,
        },
    }


def _alpha_closeout() -> dict:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
    }


def _run_status() -> dict:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "provider_network_calls_executed": False,
            "promotion_or_freeze_or_holdout_executed": False,
            "paper_or_live_executed": False,
            "cleanup_or_git_publication_executed": False,
        },
    }


def _base_repo(tmp_path: Path) -> Path:
    _write_json(tmp_path, TEST_INPUTS["statistical_closeout_boundary"], _statistical_closeout_boundary())
    _write_json(tmp_path, TEST_INPUTS["after_phase2_gap_map"], _after_phase2_gap_map())
    _write_json(tmp_path, TEST_INPUTS["master_audit_closeout"], _master_audit_closeout())
    _write_json(tmp_path, TEST_INPUTS["model_trust_audit"], _model_trust_audit())
    _write_json(tmp_path, TEST_INPUTS["alpha_closeout"], _alpha_closeout())
    _write_json(tmp_path, TEST_INPUTS["run_status"], _run_status())
    _write_text(tmp_path, TEST_INPUTS["adversarial_audit"], "Fail / Blocked.\n")
    return tmp_path


def _build(tmp_path: Path) -> dict:
    repo_root = _base_repo(tmp_path)
    return builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )


def test_terminal_closeout_refresh_passes_current_closed_blocked_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == builder.PASS_STATUS
    summary = report["summary"]
    assert summary["terminal_closeout_decision"] == builder.TERMINAL_CLOSEOUT_DECISION
    assert summary["data_integrity"] == "PASS"
    assert summary["statistical_validity"] == "FAIL"
    assert summary["operational_resilience"] == "FAIL"
    assert summary["full_master_audit_accepted"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    assert summary["paper_live_ready"] is False
    assert summary["production_ready"] is False


def test_missing_closeout_boundary_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    (repo_root / TEST_INPUTS["statistical_closeout_boundary"]).unlink()

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["model_trust_ready"] is False


def test_data_integrity_not_pass_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _after_phase2_gap_map()
    payload["summary"]["gap_area_statuses"]["data_integrity"] = "FAIL"
    payload["summary"]["data_integrity_ready"] = False
    _write_json(repo_root, TEST_INPUTS["after_phase2_gap_map"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS


def test_statistical_or_operational_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _after_phase2_gap_map()
    payload["summary"]["gap_area_statuses"]["statistical_validity"] = "PASS"
    payload["summary"]["statistical_validity_ready"] = True
    _write_json(repo_root, TEST_INPUTS["after_phase2_gap_map"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["statistical_validity_ready"] is False


def test_model_trust_or_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _master_audit_closeout()
    payload["summary"]["model_trust_ready"] = True
    payload["summary"]["promotion_allowed"] = True
    _write_json(repo_root, TEST_INPUTS["master_audit_closeout"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


def test_model_trust_non_approval_true_fails_closed(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    payload = _model_trust_audit()
    payload["non_approval"]["promotion"] = True
    _write_json(repo_root, TEST_INPUTS["model_trust_audit"], payload)

    report = builder.build_report(
        repo_root=repo_root,
        reports_root=repo_root / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["model_trust_ready"] is False


def test_report_local_non_approval_flag_true_fails_closed(tmp_path: Path) -> None:
    report = builder.build_report(
        repo_root=_base_repo(tmp_path),
        reports_root=tmp_path / builder.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
        non_approval_overrides={"phase8_refresh_executed": True},
    )

    assert report["status"] == builder.FAIL_STATUS
    assert report["summary"]["promotion_allowed"] is False


def test_writes_exact_report_pair_under_master_audit(tmp_path: Path) -> None:
    repo_root = _base_repo(tmp_path)
    reports_root = repo_root / builder.DEFAULT_REPORTS_ROOT
    report = builder.build_report(
        repo_root=repo_root,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=TEST_INPUTS,
    )

    json_path, md_path = builder.write_report(report, reports_root)

    assert json_path.name == builder.REPORT_JSON
    assert md_path.name == builder.REPORT_MD
    assert sorted(path.name for path in reports_root.iterdir()) == [
        builder.REPORT_JSON,
        builder.REPORT_MD,
    ]
    assert "reports/master_audit" in reports_root.as_posix()
