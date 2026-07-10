from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_research_factory_readiness as audit


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _row(
    audit_area: str,
    run_status: str,
    detail_status: str,
    evidence_state: str,
) -> dict[str, object]:
    return {
        "audit_area": audit_area,
        "run_status": run_status,
        "detail_status": detail_status,
        "evidence_state": evidence_state,
        "scope": "test scope",
    }


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "dirty_worktree_entry_count": 55,
            "stale_or_unknown_source_hash_mismatch_count": 2,
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
        },
        "run_status_table": [
            _row("Overview", "NOT_RUN", "NOT_RUN_MASTER_AUDIT_TAB", "missing"),
            _row("Phase 1A", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 1B", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 2", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "unknown"),
            _row("Phase 3", "RUN", "RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE", "limited-scope"),
            _row("Phase 4", "RUN", "RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE", "limited-scope"),
            _row("Phase 5", "RUN", "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD", "limited-scope"),
            _row("Phase 6", "NOT_RUN", "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED", "unknown"),
            _row("Phase 7", "NOT_RUN", "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE", "missing"),
            _row("Phase 8", "RUN", "RUN_FAILING_ALPHA_PROMOTION_EVIDENCE", "current"),
            _row("Phase 9", "RUN", "RUN_LIMITED_SCOPE_ALPHA_EVIDENCE_CLOSEOUT", "limited-scope"),
            _row("Phase 10", "N/A", "N/A_NOT_APPROVED_ARTIFACT_FREEZE", "missing"),
            _row("Phase 11", "N/A", "N/A_NOT_APPROVED_FINAL_HOLDOUT", "missing"),
            _row(
                "Research Factory",
                "NOT_RUN",
                "NOT_RUN_NO_RESEARCH_FACTORY_EXECUTION_PERMISSION",
                "missing",
            ),
            _row(
                "Research Readiness",
                "NOT_RUN",
                "NOT_RUN_RESEARCH_READINESS_REVIEW_NOT_EXECUTED",
                "missing",
            ),
            _row("Production / Paper / Live", "N/A", "N/A_NOT_APPROVED_NOT_IN_SCOPE", "missing"),
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
        "summary": {"failure_count": 0},
        "non_approval": dict(audit.NON_APPROVAL),
    }


def _closeout_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY",
        "summary": {
            "closeout_classification": "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY",
            "research_factory_ready": False,
            "research_readiness_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
        },
        "non_approval": dict(audit.NON_APPROVAL),
    }


def _phase_payload(status: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": {"failure_count": 0},
        "non_approval": dict(audit.NON_APPROVAL),
    }


def _phase_payloads() -> dict[str, dict[str, object]]:
    payloads = {
        "phase1b_reconciliation_json": _phase_payload(
            "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY"
        )
    }
    for phase in range(2, 12):
        payloads[f"phase{phase}_reconciliation_json"] = _phase_payload(
            f"PASS_MASTER_AUDIT_PHASE{phase}_RECONCILIATION_REPORT_ONLY"
        )
    return payloads


def _gap_payload(
    *,
    status: str,
    score_eligible: bool,
    source_hashes: dict[str, str] | None = None,
) -> dict[str, object]:
    source_hashes = {"evidence.json": "abc123"} if source_hashes is None else source_hashes
    return {
        "status": "PASS_MASTER_AUDIT_GAP_REMEDIATION_EVIDENCE_MAP_REPORT_ONLY",
        "summary": {
            "gap_area_statuses": {
                "data_integrity": status,
                "statistical_validity": status,
                "operational_resilience": status,
            }
        },
        "outputs": {"json": audit.DEFAULT_GAP_REMEDIATION.as_posix()},
        "gap_maps": {
            area: {
                "status": status,
                "score_eligible": score_eligible,
                "checks": [
                    {
                        "check_id": f"{area}_check",
                        "status": status,
                        "source_hashes": source_hashes,
                    }
                ],
            }
            for area in ("data_integrity", "statistical_validity", "operational_resilience")
        },
    }


def _payloads() -> dict[str, dict[str, object]]:
    return {
        "run_status": _run_status_payload(),
        "overview": _overview_payload(),
        "closeout": _closeout_payload(),
        **_phase_payloads(),
    }


def _base_repo(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
    omit_path: Path | None = None,
) -> Path:
    _write_text(tmp_path / "MASTER_AUDIT.md", "Research Factory\nResearch Readiness\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "Production Deferral Gate\n")
    _write_text(tmp_path / "CODEX_HANDOFF.md", "Master Audit handoff\n")
    _write_text(
        tmp_path / "scripts" / "validation" / "build_master_audit_run_status.py",
        "# builder\n",
    )
    _write_text(
        tmp_path / "tests" / "validation" / "test_build_master_audit_run_status.py",
        "# test\n",
    )
    payloads = _payloads()
    if payload_overrides:
        payloads.update(payload_overrides)
    paths = audit.build_input_paths(
        run_status=audit.DEFAULT_RUN_STATUS,
        overview=audit.DEFAULT_OVERVIEW,
        closeout_path=audit.DEFAULT_CLOSEOUT,
    )
    for key, path in paths.items():
        if path == omit_path:
            continue
        if key in {"master_audit", "project_outline", "codex_handoff"}:
            continue
        if key.endswith("_md"):
            _write_text(tmp_path / path, "# report\n")
        else:
            _write_json(tmp_path / path, payloads[key])
    return tmp_path / audit.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, dict[str, object]] | None = None,
    git_status_lines: list[str] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return audit.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[] if git_status_lines is None else git_status_lines,
    )


def test_happy_path_passes_with_score_20_not_ready(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == audit.PASS_STATUS
    assert report["summary"]["readiness_score"] == 20
    assert report["summary"]["readiness_interpretation"] == "Not Ready"
    assert report["research_factory"]["factory_score"] == 20
    assert report["research_readiness"]["scores"]["total"] == 20
    assert report["summary"]["research_factory_ready"] is False
    assert report["summary"]["research_readiness_ready"] is False
    assert all(value is False for value in report["non_approval"].values())
    assert report["research_readiness"]["gap_remediation"]["available"] is False


def test_lifecycle_stages_are_exact_and_non_authorizing(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert [row["stage"] for row in report["research_factory"]["lifecycle_stages"]] == [
        "audit",
        "generate_data",
        "generate_labels",
        "generate_features",
        "create_wfa_splits",
        "train",
        "predict",
        "evaluate",
        "stress_test",
        "score",
        "promote_reject",
    ]
    promote_row = report["research_factory"]["lifecycle_stages"][-1]
    assert promote_row["classification"] == "Partially Automated"
    assert "promotion_executed" in promote_row["blocked_actions"]
    assert report["summary"]["promotion_allowed"] is False


def test_missing_required_input_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path, omit_path=audit.DEFAULT_OVERVIEW)

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == audit.FAIL_STATUS
    assert any("missing required" in failure for failure in report["failures"])


def test_upstream_forbidden_action_flag_fails_closed(tmp_path: Path) -> None:
    bad_closeout = _closeout_payload()
    bad_closeout["non_approval"]["paper_live_executed"] = True

    report = _build(tmp_path, payload_overrides={"closeout": bad_closeout})

    assert report["status"] == audit.FAIL_STATUS
    assert any("forbidden" in failure for failure in report["failures"])


def test_clean_git_status_marks_embedded_dirty_count_stale_not_ready(tmp_path: Path) -> None:
    report = _build(tmp_path, git_status_lines=[])

    assert report["status"] == audit.PASS_STATUS
    assert report["summary"]["current_git_status_short_count"] == 0
    assert report["summary"]["embedded_dirty_worktree_entry_count"] == 55
    assert {
        item["code"] for item in report["stale_evidence"]
    } == {"STALE_EMBEDDED_LEDGER_STATE_SUPERSEDED_FOR_WORKTREE_CLEANLINESS_ONLY"}
    assert report["summary"]["readiness_score"] == 20


def test_phase_gaps_are_not_established(tmp_path: Path) -> None:
    report = _build(tmp_path)

    phase_gaps = report["research_readiness"]["phase_gaps"]
    assert [gap["audit_area"] for gap in phase_gaps] == [
        "Overview",
        "Phase 1A",
        "Phase 1B",
        "Phase 2",
        "Phase 6",
        "Phase 7",
    ]
    assert {gap["claim_label"] for gap in phase_gaps} == {"Not established"}
    assert {gap["run_status"] for gap in phase_gaps} <= {"NOT_RUN"}


def test_production_paper_live_freeze_holdout_remain_na(tmp_path: Path) -> None:
    report = _build(tmp_path)

    blocked = report["research_readiness"]["blocked_readiness_categories"]
    assert blocked["production"] == "N/A - not approved / not in scope"
    assert blocked["paper_live"] == "N/A - not approved / not in scope"
    assert blocked["promotion"] == "N/A - not approved / not in scope"
    assert blocked["artifact_freeze"] == "N/A - not approved / not in scope"
    assert blocked["final_holdout"] == "N/A - not approved / not in scope"
    assert report["summary"]["production_ready"] is False
    assert report["summary"]["paper_live_ready"] is False


def test_research_readiness_ledger_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_run_status = copy.deepcopy(_run_status_payload())
    for row in bad_run_status["run_status_table"]:
        if row["audit_area"] == "Research Readiness":
            row["run_status"] = "RUN"
            row["detail_status"] = "RUN_RESEARCH_READY"

    report = _build(tmp_path, payload_overrides={"run_status": bad_run_status})

    assert report["status"] == audit.FAIL_STATUS
    assert any("ledger rows" in failure for failure in report["failures"])


def test_main_writes_exact_json_and_markdown_pair(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = audit.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        audit.REPORT_JSON,
        audit.REPORT_MD,
    ]
    payload = json.loads((reports_root / audit.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["readiness_score"] == 20
    assert payload["research_readiness"]["score_interpretation"] == "Not Ready"


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == audit.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])


def test_gap_remediation_fail_map_does_not_raise_zero_scores(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    _write_json(
        tmp_path / audit.DEFAULT_GAP_REMEDIATION,
        _gap_payload(status="FAIL", score_eligible=False),
    )

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    scores = report["research_readiness"]["scores"]
    assert report["status"] == audit.PASS_STATUS
    assert scores["total"] == 20
    assert scores["data_integrity"] == 0
    assert scores["statistical_validity"] == 0
    assert scores["operational_resilience"] == 0
    gap_summary = report["research_readiness"]["gap_remediation"]
    assert gap_summary["available"] is True
    assert gap_summary["gap_area_statuses"]["data_integrity"] == "FAIL"
    assert gap_summary["score_eligible_areas"] == []


def test_gap_remediation_pass_requires_source_hashes_for_score(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    _write_json(
        tmp_path / audit.DEFAULT_GAP_REMEDIATION,
        _gap_payload(status="PASS", score_eligible=True, source_hashes={}),
    )

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    scores = report["research_readiness"]["scores"]
    assert scores["total"] == 20
    assert scores["data_integrity"] == 0
    assert report["research_readiness"]["gap_remediation"]["score_eligible_areas"] == []


def test_gap_remediation_pass_with_hashes_adds_evidence_tied_scores(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    _write_json(
        tmp_path / audit.DEFAULT_GAP_REMEDIATION,
        _gap_payload(status="PASS", score_eligible=True),
    )

    report = audit.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    scores = report["research_readiness"]["scores"]
    assert scores["total"] == 35
    assert scores["data_integrity"] == 5
    assert scores["statistical_validity"] == 5
    assert scores["operational_resilience"] == 5
    assert report["summary"]["score_criteria_met"][-3:] == [
        "data_integrity_gap_remediation_pass",
        "statistical_validity_gap_remediation_pass",
        "operational_resilience_gap_remediation_pass",
    ]
