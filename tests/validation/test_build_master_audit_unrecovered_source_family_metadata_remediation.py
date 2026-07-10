from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_source_report_recovery_disposition_plan as source_plan,
)
from scripts.validation import (
    build_master_audit_unrecovered_source_family_metadata_remediation as plan,
)
from tests.validation import (
    test_build_master_audit_source_report_recovery_disposition_plan as source_fixture,
)


def _write_source_disposition_report(tmp_path: Path) -> Path:
    reports_root = source_fixture._write_backfill_report(tmp_path)
    _add_family_metadata_to_registry(tmp_path)
    report = source_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    source_plan.write_report(report, reports_root)
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _read_json(tmp_path: Path, relative_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, relative_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / relative_path
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_family_metadata_to_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / plan.TARGET_REGISTRY
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    hypotheses = registry["hypotheses"]
    assert isinstance(hypotheses, list)
    for row in hypotheses:
        assert isinstance(row, dict)
        hypothesis_id = row["target_hypothesis_id"]
        row["target_family"] = f"{hypothesis_id}_family"
        row["scope"] = {
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "markets": ["ES"],
            "years": [2023, 2024],
        }
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _write_source_disposition_report(tmp_path)
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        **kwargs,
    )


def test_unrecovered_source_family_metadata_plan_passes_current_blocked_state(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["candidate_trial_search_ledger_row_count"] == 27
    assert summary["source_report_disposition_note_count"] == 14
    assert summary["missing_registry_json_source_report_ref_count"] == 14
    assert summary["unrecovered_source_report_count"] == 14
    assert summary["append_only_backfill_allowed"] is False
    assert summary["ledger_mutation_allowed"] is False
    assert summary["source_report_restore_executed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    assert len(report["unrecovered_source_report_disposition_notes"]) == 14
    assert len(report["family_metadata_remediation_rows"]) == 27
    assert summary["search_family_status_counts"][plan.PROPOSED_FAMILY] == 22
    assert summary["search_family_status_counts"][plan.UNRESOLVED] == 5
    assert summary["multiple_testing_family_status_counts"][plan.PROPOSED_FAMILY] == 22
    assert all(
        row["eligible_for_future_append_only_backfill"] is False
        for row in report["family_metadata_remediation_rows"]
    )


def test_missing_source_disposition_report_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    (tmp_path / plan.SOURCE_DISPOSITION_REPORT).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("source disposition" in failure.lower() for failure in report["failures"])


def test_recovered_source_disposition_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    payload = _read_json(tmp_path, plan.SOURCE_DISPOSITION_REPORT)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["source_report_restore_executed"] = True
    _write_json(tmp_path, plan.SOURCE_DISPOSITION_REPORT, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("restored" in failure.lower() for failure in report["failures"])


def test_malformed_trial_status_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    (tmp_path / plan.TARGET_TRIAL_STATUSES).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_candidate_row_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    payload = _read_json(tmp_path, plan.SCHEMA_REMEDIATION)
    rows = payload["candidate_trial_search_ledger_rows"]
    assert isinstance(rows, list)
    payload["candidate_trial_search_ledger_rows"] = rows[:-1]
    _write_json(tmp_path, plan.SCHEMA_REMEDIATION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("candidate rows" in failure.lower() for failure in report["failures"])


def test_missing_registry_family_metadata_stays_unresolved(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    registry = _read_json(tmp_path, plan.TARGET_REGISTRY)
    hypotheses = registry["hypotheses"]
    assert isinstance(hypotheses, list)
    first = hypotheses[0]
    assert isinstance(first, dict)
    first.pop("target_family")
    _write_json(tmp_path, plan.TARGET_REGISTRY, registry)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.PASS_STATUS
    unresolved_rows = [
        row for row in report["family_metadata_remediation_rows"]
        if row["hypothesis_id"] == first["target_hypothesis_id"]
    ]
    assert unresolved_rows
    assert all(row["search_family_id"]["status"] == plan.UNRESOLVED for row in unresolved_rows)


def test_write_approval_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        approval_overrides={"ledger_mutation_executed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)
    payload = _read_json(tmp_path, plan.SCHEMA_REMEDIATION)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["promotion_allowed"] = True
    _write_json(tmp_path, plan.SCHEMA_REMEDIATION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("no longer blocked" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _write_source_disposition_report(tmp_path)

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
    assert payload["summary"]["append_only_backfill_allowed"] is False
    assert payload["summary"]["source_report_restore_executed"] is False
    assert payload["summary"]["promotion_allowed"] is False
