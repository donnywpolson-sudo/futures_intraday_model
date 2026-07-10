from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_closeout as closeout


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
        },
        "run_status_table": [
            {
                "audit_area": "Research Factory",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION",
                "evidence_state": "missing",
            },
            {
                "audit_area": "Research Readiness",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED",
                "evidence_state": "missing",
            },
            {
                "audit_area": "Production / Paper / Live",
                "run_status": "N/A",
                "detail_status": "N/A_NOT_APPROVED_NOT_IN_SCOPE",
                "evidence_state": "missing",
            },
            {
                "audit_area": "Phase 10",
                "run_status": "N/A",
                "detail_status": "N/A_NOT_APPROVED_ARTIFACT_FREEZE",
                "evidence_state": "missing",
            },
            {
                "audit_area": "Phase 11",
                "run_status": "N/A",
                "detail_status": "N/A_NOT_APPROVED_FINAL_HOLDOUT",
                "evidence_state": "missing",
            },
        ],
    }


def _phase_payload(name: str, status: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": {
            "failure_count": 0,
            f"{name}_master_audit_status": f"RUN_LIMITED_SCOPE_{name.upper()}_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
            "freeze_executed": False,
            "holdout_executed": False,
        },
        "non_approval": {
            "cleanup_executed": False,
            "freeze_executed": False,
            "holdout_executed": False,
            "paper_live_executed": False,
            "promotion_executed": False,
            "provider_network_calls_executed": False,
            "wfa_modeling_executed": False,
        },
    }


def _phase_payloads() -> dict[str, dict[str, object]]:
    payloads = {
        "phase1b_reconciliation": _phase_payload(
            "phase1b", "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        )
    }
    for phase in range(2, 12):
        payloads[f"phase{phase}_reconciliation"] = _phase_payload(
            f"phase{phase}", f"PASS_MASTER_AUDIT_PHASE{phase}_RECONCILIATION_REPORT_ONLY"
        )
    payloads["phase8_reconciliation"]["summary"].update(
        {
            "phase8_master_audit_status": "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE",
            "research_alpha_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
        }
    )
    payloads["phase9_reconciliation"]["summary"].update(
        {
            "phase9_master_audit_status": "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT",
            "alpha_closeout_verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
            "future_modeling_allowed": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
        }
    )
    payloads["phase10_reconciliation"]["summary"].update(
        {
            "phase10_master_audit_status": "N/A_NOT_APPROVED_ARTIFACT_FREEZE",
            "phase10_full_master_audit_accepted": False,
            "artifact_freeze_ready": False,
            "artifact_freeze_allowed": False,
            "freeze_executed": False,
            "frozen_manifest_written": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
        }
    )
    payloads["phase10_reconciliation"]["non_approval"].update(
        {
            "artifact_freeze_command_executed": False,
            "artifact_freeze_manifest_written": False,
        }
    )
    payloads["phase11_reconciliation"]["summary"].update(
        {
            "phase10_master_audit_status": "N/A_NOT_APPROVED_ARTIFACT_FREEZE",
            "phase11_master_audit_status": "N/A_NOT_APPROVED_FINAL_HOLDOUT",
            "phase11_full_master_audit_accepted": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "final_holdout_allowed": False,
            "final_holdout_executed": False,
            "current_frozen_manifest_accepted": False,
            "frozen_manifest_written": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "holdout_allowed": False,
            "paper_live_allowed": False,
        }
    )
    payloads["phase11_reconciliation"]["non_approval"].update(
        {
            "artifact_freeze_command_executed": False,
            "artifact_freeze_manifest_written": False,
            "final_holdout_guard_executed": False,
            "final_holdout_report_written": False,
            "final_holdout_executed": False,
        }
    )
    return payloads


def _phase8_decision_payload() -> dict[str, object]:
    return {
        "run": closeout.RUN_ID,
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_gate": {"promotion_blocker_count": 30},
        "final_holdout_touched": False,
        "used_final_holdout_for_tuning": False,
        "blockers": [f"blocker-{idx}" for idx in range(30)],
    }


def _alpha_closeout_payload() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
        "run_id": closeout.RUN_ID,
        "terminal_fail_count": 5,
        "missing_required_evidence_count": 11,
        "modeling_pause_required": True,
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "non_approval": {
            "artifact_freeze": False,
            "cleanup": False,
            "final_holdout": False,
            "live": False,
            "paper": False,
            "phase8_refresh": False,
            "promotion": False,
            "provider_downloads": False,
            "rescue_tuning": False,
            "source_tests": False,
            "staging_commit_push": False,
            "target_discovery": False,
            "wfa_modeling": False,
        },
    }


def _payloads() -> dict[str, dict[str, object]]:
    payloads = _phase_payloads()
    payloads.update(
        {
            "run_status": _run_status_payload(),
            "overview": {
                "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
                "summary": {"failure_count": 0},
            },
            "phase8_decision": _phase8_decision_payload(),
            "alpha_closeout": _alpha_closeout_payload(),
        }
    )
    return payloads


def _base_repo(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> Path:
    _write_text(
        tmp_path / "MASTER_AUDIT.md",
        "Phase 10\nPhase 11\nResearch Readiness\nProduction / Paper / Live\npaper/live\n",
    )
    _write_text(
        tmp_path / "PROJECT_OUTLINE.md",
        "Phase 11 cannot run until Phase 10 writes a frozen manifest\n"
        "This repository must not make live-trading or paper-trading readiness claims\n",
    )
    _write_text(tmp_path / "CODEX_HANDOFF.md", "Master Audit closeout/readiness rollup\n")
    payloads = _payloads()
    if payload_overrides:
        payloads.update(payload_overrides)
    for key, path in closeout.REQUIRED_INPUTS.items():
        if key in {"master_audit", "project_outline", "codex_handoff"}:
            continue
        _write_json(tmp_path / path, payloads[key])
    return tmp_path / closeout.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return closeout.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_closeout_passes_as_report_only_blocked_not_ready(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == closeout.PASS_STATUS
    assert report["summary"]["closeout_classification"] == "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY"
    assert report["summary"]["full_master_audit_accepted"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["artifact_freeze_ready"] is False
    assert report["summary"]["final_holdout_ready"] is False
    assert report["summary"]["paper_live_ready"] is False
    assert report["summary"]["production_ready"] is False
    assert report["summary"]["prediction_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_phase8_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_decision = _phase8_decision_payload()
    bad_decision["promoted"] = True

    report = _build(tmp_path, payload_overrides={"phase8_decision": bad_decision})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("Phase 8/9" in failure for failure in report["failures"])


def test_phase8_final_holdout_touch_fails_closed(tmp_path: Path) -> None:
    bad_decision = _phase8_decision_payload()
    bad_decision["final_holdout_touched"] = True

    report = _build(tmp_path, payload_overrides={"phase8_decision": bad_decision})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("Phase 8/9" in failure for failure in report["failures"])


def test_phase10_freeze_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_phase10 = copy.deepcopy(_phase_payloads()["phase10_reconciliation"])
    bad_phase10["summary"]["artifact_freeze_ready"] = True

    report = _build(tmp_path, payload_overrides={"phase10_reconciliation": bad_phase10})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("Phase 10/11" in failure for failure in report["failures"])


def test_phase11_holdout_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_phase11 = copy.deepcopy(_phase_payloads()["phase11_reconciliation"])
    bad_phase11["summary"]["final_holdout_ready"] = True

    report = _build(tmp_path, payload_overrides={"phase11_reconciliation": bad_phase11})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("Phase 10/11" in failure for failure in report["failures"])


def test_research_readiness_ledger_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_run_status = _run_status_payload()
    bad_run_status["run_status_table"][1]["run_status"] = "RUN"
    bad_run_status["run_status_table"][1]["detail_status"] = "RUN_RESEARCH_READY"

    report = _build(tmp_path, payload_overrides={"run_status": bad_run_status})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("ledger rows" in failure for failure in report["failures"])


def test_alpha_closeout_modeling_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_closeout = _alpha_closeout_payload()
    bad_closeout["future_modeling_allowed"] = True

    report = _build(tmp_path, payload_overrides={"alpha_closeout": bad_closeout})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("Phase 8/9" in failure for failure in report["failures"])


def test_upstream_forbidden_execution_flag_fails_closed(tmp_path: Path) -> None:
    bad_phase11 = copy.deepcopy(_phase_payloads()["phase11_reconciliation"])
    bad_phase11["non_approval"]["final_holdout_guard_executed"] = True

    report = _build(tmp_path, payload_overrides={"phase11_reconciliation": bad_phase11})

    assert report["status"] == closeout.FAIL_STATUS
    assert any("forbidden action" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = closeout.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        closeout.REPORT_JSON,
        closeout.REPORT_MD,
    ]
    payload = json.loads((reports_root / closeout.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["model_trust_ready"] is False
    assert payload["non_approval"]["final_holdout_guard_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = closeout.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == closeout.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
