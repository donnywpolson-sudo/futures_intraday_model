from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_trial_search_ledger_backfill_decision as plan,
)
from scripts.validation import (
    build_master_audit_trial_search_ledger_schema_remediation_plan as schema_plan,
)
from tests.validation import (
    test_build_master_audit_trial_search_ledger_schema_remediation_plan as schema_fixture,
)


def _write_schema_report(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    schema_reports_root = schema_fixture._base_repo(tmp_path)
    schema_report = schema_plan.build_report(
        repo_root=tmp_path,
        reports_root=schema_reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    schema_plan.write_report(schema_report, schema_reports_root)
    return schema_reports_root, schema_report


def _write_backfill_inputs(tmp_path: Path) -> Path:
    _write_schema_report(tmp_path)
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _read_schema_payload(tmp_path: Path) -> dict[str, object]:
    path = tmp_path / plan.SCHEMA_REMEDIATION
    return json.loads(path.read_text(encoding="utf-8"))


def _write_schema_payload(tmp_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / plan.SCHEMA_REMEDIATION
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _write_backfill_inputs(tmp_path)
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        **kwargs,
    )


def test_backfill_decision_passes_blocked_current_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["backfill_decision"] == plan.BACKFILL_DECISION
    assert summary["candidate_trial_search_ledger_row_count"] == 27
    assert summary["eligible_for_future_backfill_count"] == 0
    assert summary["blocked_row_count"] == 27
    assert summary["registry_json_source_report_ref_count"] == 21
    assert summary["present_registry_json_source_report_ref_count"] == 7
    assert summary["missing_registry_json_source_report_ref_count"] == 14
    assert summary["unresolved_field_counts"]["search_family_id"] == 27
    assert summary["unresolved_field_counts"]["multiple_testing_family_id"] == 27
    assert summary["append_only_backfill_allowed"] is False
    assert summary["write_schema_complete_rows_allowed"] is False
    assert summary["write_unresolved_marker_rows_allowed"] is False
    assert summary["ledger_mutation_executed"] is False
    assert summary["pbo_applicability_ready"] is False
    assert summary["deflated_sharpe_applicability_ready"] is False
    assert summary["multiple_testing_applicability_ready"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    assert all(
        item["eligible_for_future_backfill"] is False
        for item in report["row_level_backfill_decisions"]
    )


def test_missing_schema_remediation_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    (tmp_path / plan.SCHEMA_REMEDIATION).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("schema-remediation" in failure.lower() for failure in report["failures"])


def test_malformed_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    (tmp_path / plan.EXPERIMENT_LEDGER).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_changed_candidate_row_count_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    payload = _read_schema_payload(tmp_path)
    rows = payload["candidate_trial_search_ledger_rows"]
    assert isinstance(rows, list)
    payload["candidate_trial_search_ledger_rows"] = rows[:-1]
    _write_schema_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("count drifted" in failure.lower() for failure in report["failures"])


def test_candidate_missing_required_field_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    payload = _read_schema_payload(tmp_path)
    rows = payload["candidate_trial_search_ledger_rows"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0].pop("search_family_id")
    _write_schema_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("required fields are absent" in failure for failure in report["failures"])


def test_source_ref_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    payload = _read_schema_payload(tmp_path)
    refs = payload["source_report_reference_inventory"]
    assert isinstance(refs, list)
    payload["source_report_reference_inventory"] = refs[:-1]
    _write_schema_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("source-report reference counts drifted" in failure for failure in report["failures"])


def test_unresolved_marker_write_approval_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        approval_overrides={"write_unresolved_marker_rows_allowed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)
    payload = _read_schema_payload(tmp_path)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["promotion_allowed"] = True
    _write_schema_payload(tmp_path, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("no longer blocked" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _write_backfill_inputs(tmp_path)

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
    assert payload["summary"]["backfill_decision"] == plan.BACKFILL_DECISION
    assert payload["summary"]["append_only_backfill_allowed"] is False
    assert payload["summary"]["promotion_allowed"] is False
