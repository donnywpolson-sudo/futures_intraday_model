from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_source_report_recovery_disposition_plan as plan,
)
from scripts.validation import (
    build_master_audit_trial_search_ledger_backfill_decision as backfill_plan,
)
from tests.validation import (
    test_build_master_audit_trial_search_ledger_backfill_decision as backfill_fixture,
)


def _write_backfill_report(tmp_path: Path) -> Path:
    reports_root = backfill_fixture._write_backfill_inputs(tmp_path)
    report = backfill_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    backfill_plan.write_report(report, reports_root)
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _read_backfill_payload(tmp_path: Path) -> dict[str, object]:
    path = tmp_path / plan.BACKFILL_DECISION_REPORT
    return json.loads(path.read_text(encoding="utf-8"))


def _write_backfill_payload(tmp_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / plan.BACKFILL_DECISION_REPORT
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _write_backfill_report(tmp_path)
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        **kwargs,
    )


def test_source_report_disposition_plan_passes_current_blocked_state(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["missing_registry_json_source_report_ref_count"] == 14
    assert summary["present_registry_json_source_report_ref_count"] == 7
    assert summary["registry_json_source_report_ref_count"] == 21
    assert summary["disposition_counts"] == {plan.UNRECOVERED: 14}
    assert summary["append_only_backfill_allowed"] is False
    assert summary["ledger_mutation_allowed"] is False
    assert summary["source_report_restore_executed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    assert len(report["missing_source_report_dispositions"]) == 14
    assert all(
        row["recommended_disposition"] == plan.UNRECOVERED
        for row in report["missing_source_report_dispositions"]
    )


def test_git_history_marks_row_recoverable_without_restoring(
    tmp_path: Path,
) -> None:
    reports_root = _write_backfill_report(tmp_path)
    payload = _read_backfill_payload(tmp_path)
    missing_paths = payload["summary"]["missing_source_report_paths"]
    assert isinstance(missing_paths, list)
    first_path = str(missing_paths[0])

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        git_history_overrides={first_path: ["abc123"]},
    )

    assert report["status"] == plan.PASS_STATUS
    assert report["summary"]["disposition_counts"][plan.RECOVERABLE_GIT] == 1
    row = next(
        item
        for item in report["missing_source_report_dispositions"]
        if item["missing_source_report_path"] == first_path
    )
    assert row["recommended_disposition"] == plan.RECOVERABLE_GIT
    assert row["git_history_commits"] == ["abc123"]
    assert row["current_path_exists"] is False


def test_missing_backfill_report_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)
    (tmp_path / plan.BACKFILL_DECISION_REPORT).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("backfill decision" in failure.lower() for failure in report["failures"])


def test_source_ref_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)
    payload = _read_backfill_payload(tmp_path)
    refs = payload["source_report_reference_inventory"]
    assert isinstance(refs, list)
    payload["source_report_reference_inventory"] = refs[:-1]
    _write_backfill_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("dropped" in failure.lower() or "counts drifted" in failure.lower() for failure in report["failures"])


def test_malformed_trial_status_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)
    (tmp_path / plan.TARGET_TRIAL_STATUSES).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)
    payload = _read_backfill_payload(tmp_path)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["promotion_allowed"] = True
    _write_backfill_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("no longer blocked" in failure.lower() for failure in report["failures"])


def test_write_or_restore_approval_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        approval_overrides={"source_report_restore_executed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _write_backfill_report(tmp_path)

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["source_report_restore_executed"] is False
    assert payload["summary"]["append_only_backfill_allowed"] is False
    assert payload["summary"]["promotion_allowed"] is False
