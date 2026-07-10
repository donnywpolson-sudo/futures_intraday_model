from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_overview as overview


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _row(area: str, status: str, detail: str, evidence_state: str, evidence: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "audit_area": area,
        "run_status": status,
        "detail_status": detail,
        "evidence_state": evidence_state,
        "accepted_evidence": evidence or [],
        "scope": f"{area} scope",
        "notes": [f"{area} note"],
    }


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "run_status_counts": {"RUN": 6, "NOT_RUN": 8, "N/A": 3},
            "evidence_state_counts": {"current": 2, "limited-scope": 4, "missing": 7, "unknown": 4},
            "stale_or_unknown_source_hash_mismatch_count": 2,
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "phase_audits_executed": False,
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "provider_network_calls_executed": False,
        },
        "run_status_table": [
            _row("Master Audit Evidence Inventory / Run-Status", "RUN", "RUN_REPORT_ONLY_CURRENT_COMMAND", "current"),
            _row("Overview", "NOT_RUN", "NOT_RUN_MASTER_AUDIT_TAB", "missing"),
            _row("Phase 1A", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 1B", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 2", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 3", "RUN", "RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE", "limited-scope"),
            _row("Phase 4", "RUN", "RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE", "limited-scope"),
            _row("Phase 5", "RUN", "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD", "limited-scope"),
            _row(
                "Phase 6",
                "NOT_RUN",
                "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
                "unknown",
                [{"path": "reports/phase8/example.json"}],
            ),
            _row("Phase 7", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "missing"),
            _row(
                "Phase 8",
                "RUN",
                "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE",
                "current",
                [{"path": "reports/phase8/decision.json"}],
            ),
            _row(
                "Phase 9",
                "RUN",
                "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT",
                "limited-scope",
                [{"path": "reports/model_trust_audit/closeout.json"}],
            ),
            _row("Phase 10", "N/A", "N/A_NOT_APPROVED_ARTIFACT_FREEZE", "missing"),
            _row("Phase 11", "N/A", "N/A_NOT_APPROVED_FINAL_HOLDOUT", "missing"),
            _row("Research Factory", "NOT_RUN", "NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION", "missing"),
            _row("Research Readiness", "NOT_RUN", "NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED", "missing"),
            _row("Production / Paper / Live", "N/A", "N/A_NOT_APPROVED_NOT_IN_SCOPE", "missing"),
        ],
        "stale_or_unknown_source_hash_mismatches": [
            {"path": "configs/models.yaml", "source": "models_config"},
            {"path": "configs/alpha_tiered.yaml", "source": "profile_config"},
        ],
    }


def _base_repo(tmp_path: Path, payload: dict[str, object] | None = None) -> dict[str, Path]:
    for name in ("MASTER_AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"):
        _write_text(tmp_path / name)
    run_status_path = tmp_path / overview.DEFAULT_RUN_STATUS
    _write_json(run_status_path, payload or _run_status_payload())
    return {
        "run_status": run_status_path,
        "reports_root": tmp_path / overview.DEFAULT_REPORTS_ROOT,
    }


def _build(tmp_path: Path, payload: dict[str, object] | None = None) -> dict[str, object]:
    paths = _base_repo(tmp_path, payload=payload)
    return overview.build_report(
        repo_root=tmp_path,
        run_status_path=paths["run_status"],
        reports_root=paths["reports_root"],
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_overview_builds_all_required_sections_without_executing_forbidden_actions(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == overview.PASS_STATUS
    assert report["summary"]["phase_audits_executed"] is False
    assert report["summary"]["data_model_commands_executed"] is False
    assert sorted(report["overview_sections"]) == sorted(overview.OVERVIEW_SECTION_KEYS)
    assert report["overview_sections"]["A_executive_summary"]["verdict"] == "BLOCKED_FOR_MODEL_TRUST_AND_TRADING_USE"
    assert report["overview_sections"]["H_readiness_score"]["model_trust_readiness_score"]["score"] == 0
    assert report["overview_sections"]["H_readiness_score"]["paper_live_readiness_score"]["score"] == 0


def test_overview_preserves_split_and_line_blockers(tmp_path: Path) -> None:
    report = _build(tmp_path)
    findings = report["overview_sections"]["D_risk_assessment"]["findings"]

    assert any(item["finding_id"] == "overview-001-current-line-closed" for item in findings)
    assert any(item["finding_id"] == "overview-002-split-research-only" for item in findings)
    assert report["summary"]["current_line_classification"] == "closed_no_alpha_evidence"
    assert report["summary"]["current_split_classification"] == "same_fold_rolling_retraining_research_only"


def test_overview_fails_if_run_status_forbidden_flags_are_true(tmp_path: Path) -> None:
    payload = copy.deepcopy(_run_status_payload())
    payload["summary"]["wfa_modeling_executed"] = True

    report = _build(tmp_path, payload=payload)

    assert report["status"] == overview.FAIL_STATUS
    assert any("wfa_modeling_executed" in failure for failure in report["failures"])


def test_missing_run_status_fails_closed(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)
    paths["run_status"].unlink()

    report = overview.build_report(
        repo_root=tmp_path,
        run_status_path=paths["run_status"],
        reports_root=paths["reports_root"],
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == overview.FAIL_STATUS
    assert any("run-status" in failure or "required input unavailable" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)

    exit_code = overview.main(
        [
            "--repo-root",
            str(tmp_path),
            "--run-status",
            str(paths["run_status"]),
            "--reports-root",
            str(paths["reports_root"]),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in paths["reports_root"].iterdir()) == [
        overview.REPORT_JSON,
        overview.REPORT_MD,
    ]
    payload = json.loads((paths["reports_root"] / overview.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["wfa_modeling_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)

    report = overview.build_report(
        repo_root=tmp_path,
        run_status_path=paths["run_status"],
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == overview.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
