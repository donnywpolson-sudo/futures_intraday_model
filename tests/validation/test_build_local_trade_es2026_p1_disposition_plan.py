from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_blocker_proposal as blocker_gate
from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as readiness_review
from scripts.validation import build_local_trade_es2026_p1_disposition_plan as disposition
from scripts.validation import build_local_trade_es2026_p1_workflow_status as workflow_status
from scripts.validation import build_local_trade_optional_archive_inventory as optional_inventory


def _raw_quality(
    *,
    status: str = "FAIL",
    market: str = "ES",
    year: int = 2026,
    reason: str = "degraded threshold breached: rows_pct=1.74227 bars=2760 sessions=3",
) -> dict[str, object]:
    return {
        "stage": "phase2_readiness_raw_drilldown",
        "status": status,
        "selected_market_year_count": 1,
        "selected_market_years": [{"market": market, "year": year}],
        "drilldowns": [
            {
                "market": market,
                "year": year,
                "raw_read_status": "PASS",
                "degraded_bar_rows": 2760,
                "degraded_rows_pct": 1.74227,
                "degraded_session_rows": 3,
                "statistics_enrichment_missing_rows": 6,
                "statistics_enrichment_stale_rows": 6,
                "top_blocker_reason": reason,
            }
        ],
    }


def _write_raw_quality(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v2" / "ES_2026_raw_quality.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload or _raw_quality()), encoding="utf-8")
    return path


def _blocker_report(
    *,
    status: str = blocker_gate.STATUS_READY,
    proposal_items: int = 1,
    market: str = "ES",
    year: int = 2026,
    profile: str = "tier_3_forward",
) -> dict[str, object]:
    return {
        "summary": {
            "stage": blocker_gate.STAGE,
            "status": status,
            "market": market,
            "year": year,
            "profile": profile,
            "proposal_item_count": proposal_items,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
        },
        "proposal_items": [{} for _ in range(proposal_items)],
        "source_evidence": {
            "workflow_status": {
                "status": workflow_status.STATUS_NO_GO,
                "current_gate": "candidate_readiness_execution",
                "current_gate_status": "NO_GO_ES2026_P1_CANDIDATE_READINESS_EXECUTION",
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
            },
            "candidate_readiness_review": {
                "status": readiness_review.STATUS_NO_GO,
                "expected_readiness_output_count": 8,
                "ignored_expected_readiness_output_count": 8,
                "unignored_expected_readiness_output_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
                "failure_count": 1,
            },
            "optional_archive_inventory": {
                "status": optional_inventory.STATUS_READY,
                "ready_market_count": 33,
                "expected_market_count": 33,
                "archive_count": 66,
                "invalid_archive_count": 0,
                "generated_output_count": 0,
                "staged_generated_path_count": 0,
            },
            "raw_quality_report": "reports/pipeline_audit/repair_plan_v2/ES_2026_raw_quality.json",
        },
    }


def _build(
    tmp_path: Path,
    *,
    blocker: dict[str, object] | None = None,
    raw_quality_payload: dict[str, object] | None = None,
    raw_quality_path: Path | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v2"
    raw_quality_report = raw_quality_path or _write_raw_quality(tmp_path, raw_quality_payload)
    return disposition.build_report(
        repo_root=tmp_path,
        work_order_report=reports_root / "work_order.json",
        drilldown_report=reports_root / "drilldown.json",
        checkpoint_jsonl=reports_root / "checkpoint.jsonl",
        repair_reports_root=reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_p1_repair_candidate",
        output_root=tmp_path / "data" / "causal_es2026_p1_candidate",
        raw_alignment_report=reports_root / "candidate_raw_alignment.json",
        raw_quality_report=raw_quality_report,
        blocker_proposal_report=blocker or _blocker_report(),
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
    )


def test_builds_console_only_fail_closed_disposition_plan(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == disposition.STATUS_READY
    assert report["summary"]["disposition_option_count"] == 3
    assert report["summary"]["recommended_option"] == "repair_path"
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert report["summary"]["accepted_warning_packet_approved"] is False
    assert report["summary"]["exclusion_approved"] is False

    options = {item["option"]: item for item in report["disposition_options"]}
    assert list(options) == ["repair_path", "accepted_warning_policy", "es2026_exclusion"]
    assert options["repair_path"]["recommendation"] == "PREFERRED_DEFAULT"
    assert "degraded raw-quality review" in options["repair_path"]["required_evidence_before_execution"][0]
    assert options["accepted_warning_policy"]["option_status"] == "CRITERIA_ONLY_NOT_ACCEPTED"
    assert "primary evidence" in options["accepted_warning_policy"]["required_evidence_before_execution"][0]
    assert options["es2026_exclusion"]["option_status"] == "DIAGNOSTIC_ONLY_NOT_EXCLUDED"
    assert "model-eligible scope" in options["es2026_exclusion"]["required_evidence_before_execution"][0]
    assert all(item["approval_state"] == "requires_separate_bounded_approval" for item in options.values())


def test_blocker_proposal_not_ready_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        blocker=_blocker_report(status=blocker_gate.STATUS_NO_GO, proposal_items=0),
    )

    assert report["summary"]["status"] == disposition.STATUS_NO_GO
    assert report["summary"]["disposition_option_count"] == 0
    assert any(
        check["name"] == "blocker_proposal_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_non_fail_raw_quality_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        raw_quality_payload=_raw_quality(status="PASS", reason="not a degraded threshold failure"),
    )

    assert report["summary"]["status"] == disposition.STATUS_NO_GO
    assert any(
        check["name"] == "raw_quality_degraded_threshold_failure_present"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_wrong_raw_quality_scope_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, raw_quality_payload=_raw_quality(market="NQ", year=2026))

    assert report["summary"]["status"] == disposition.STATUS_NO_GO
    assert any(
        check["name"] == "raw_quality_exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_raw_quality_report_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "reports" / "missing_raw_quality.json"

    report = _build(tmp_path, raw_quality_path=missing)

    assert report["summary"]["status"] == disposition.STATUS_NO_GO
    assert any(
        check["name"] == "raw_quality_report_readable"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_artifacts_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/generated.json"])

    assert report["summary"]["status"] == disposition.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_disposition_packet_includes_options_and_hygiene(tmp_path: Path) -> None:
    report = _build(tmp_path)

    packet = disposition.disposition_packet(report)

    assert packet["status"] == disposition.STATUS_READY
    assert packet["recommended_option"] == "repair_path"
    assert [item["option"] for item in packet["disposition_options"]] == [
        "repair_path",
        "accepted_warning_policy",
        "es2026_exclusion",
    ]
    assert packet["generated_artifact_hygiene"] == {
        "generated_output_count": 0,
        "staged_generated_path_count": 0,
    }


def test_cli_prints_disposition_packet_without_writing_reports(tmp_path: Path, capsys, monkeypatch) -> None:
    report = _build(tmp_path)
    monkeypatch.setattr(disposition, "build_report", lambda **kwargs: report)

    exit_code = disposition.main(["--repo-root", str(tmp_path), "--print-disposition-json"])

    output_lines = capsys.readouterr().out.splitlines()
    packet = json.loads(output_lines[-1])
    assert exit_code == 0
    assert output_lines[0].startswith(f"{disposition.STAGE} status={disposition.STATUS_READY}")
    assert "recommended_option=repair_path" in output_lines[0]
    assert packet["disposition_option_count"] == 3
    assert not list(tmp_path.glob("**/*disposition_plan*.json"))
