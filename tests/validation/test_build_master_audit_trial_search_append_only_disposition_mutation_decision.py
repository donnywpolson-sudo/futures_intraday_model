from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_trial_search_append_only_disposition_mutation_decision as plan,
)
from scripts.validation import (
    build_master_audit_unrecovered_source_family_metadata_remediation as upstream_plan,
)
from tests.validation import (
    test_build_master_audit_unrecovered_source_family_metadata_remediation as upstream_fixture,
)


def _write_upstream_report(tmp_path: Path) -> Path:
    reports_root = upstream_fixture._write_source_disposition_report(tmp_path)
    report = upstream_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    upstream_plan.write_report(report, reports_root)
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _read_json(tmp_path: Path, relative_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, relative_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / relative_path
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _write_upstream_report(tmp_path)
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        **kwargs,
    )


def test_append_only_mutation_decision_passes_blocked_current_state(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["mutation_decision"] == plan.MUTATION_DECISION
    assert summary["candidate_trial_search_ledger_row_count"] == 27
    assert summary["source_report_disposition_note_count"] == 14
    assert summary["proposed_family_metadata_row_count"] == 22
    assert summary["unresolved_family_metadata_row_count"] == 5
    assert summary["registry_disposition_update_candidate_count"] == 14
    assert summary["trial_status_append_candidate_count"] == 22
    assert summary["experiment_ledger_append_candidate_count"] == 0
    assert summary["current_wfa_phase8_statistical_append_candidate_count"] == 0
    assert summary["canonical_append_only_mutation_allowed"] is False
    assert summary["registry_mutation_allowed"] is False
    assert summary["trial_status_mutation_allowed"] is False
    assert summary["experiment_ledger_mutation_allowed"] is False
    assert summary["source_report_restore_allowed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    payload = report["draft_only_mutation_payload"]
    assert payload["canonical_write_allowed_by_this_report"] is False
    assert len(payload["blocked_unresolved_rows"]) == 5


def test_missing_upstream_report_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    (tmp_path / plan.UPSTREAM_REMEDIATION).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("upstream" in failure.lower() for failure in report["failures"])


def test_unresolved_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    payload = _read_json(tmp_path, plan.UPSTREAM_REMEDIATION)
    rows = payload["family_metadata_remediation_rows"]
    assert isinstance(rows, list)
    payload["family_metadata_remediation_rows"] = rows[:-1]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["candidate_trial_search_ledger_row_count"] = 26
    _write_json(tmp_path, plan.UPSTREAM_REMEDIATION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("counts drifted" in failure.lower() for failure in report["failures"])


def test_malformed_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    (tmp_path / plan.EXPERIMENT_LEDGER).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_unknown_trial_status_hypothesis_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    trial_path = tmp_path / plan.TARGET_TRIAL_STATUSES
    rows = [json.loads(line) for line in trial_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["hypothesis_id"] = "unknown_hypothesis"
    trial_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("identity checks" in failure.lower() for failure in report["failures"])


def test_write_approval_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        approval_overrides={"canonical_append_only_mutation_allowed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    payload = _read_json(tmp_path, plan.UPSTREAM_REMEDIATION)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["promotion_allowed"] = True
    _write_json(tmp_path, plan.UPSTREAM_REMEDIATION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("readiness" in failure.lower() or "write approval" in failure.lower() for failure in report["failures"])


def test_source_restore_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_upstream_report(tmp_path)
    payload = _read_json(tmp_path, plan.UPSTREAM_REMEDIATION)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["source_report_restore_executed"] = True
    _write_json(tmp_path, plan.UPSTREAM_REMEDIATION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("restored" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    _write_upstream_report(tmp_path)
    reports_root = tmp_path / "reports" / "master_audit" / "append_mutation_decision"

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            "reports/master_audit/append_mutation_decision",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["mutation_decision"] == plan.MUTATION_DECISION
    assert payload["summary"]["canonical_append_only_mutation_allowed"] is False
    assert payload["summary"]["promotion_allowed"] is False
