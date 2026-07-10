from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_canonical_trial_search_append_only_mutation_package as plan,
)
from scripts.validation import (
    build_master_audit_trial_search_append_only_disposition_mutation_decision as append_plan,
)
from scripts.validation import (
    build_master_audit_unresolved_row_linkage_exclusion_disposition as exclusion_plan,
)
from tests.validation import (
    test_build_master_audit_unresolved_row_linkage_exclusion_disposition as exclusion_fixture,
)


SHORT_PACKAGE_INPUTS = {
    "unresolved_disposition": Path("reports/master_audit/unresolved") / exclusion_plan.REPORT_JSON,
    "append_decision": exclusion_fixture.SHORT_APPEND_DECISION,
}


def _write_source_maps(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    exclusion_fixture._write_append_decision_report(tmp_path)
    unresolved_root = tmp_path / "reports" / "master_audit" / "unresolved"
    unresolved_report = exclusion_plan.build_report(
        repo_root=tmp_path,
        reports_root=unresolved_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": exclusion_fixture.SHORT_APPEND_DECISION},
    )
    exclusion_plan.write_report(unresolved_report, unresolved_root)
    reports_root = tmp_path / plan.DEFAULT_REPORTS_ROOT
    return reports_root, dict(SHORT_PACKAGE_INPUTS)


def _read_json(tmp_path: Path, relative_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, relative_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / relative_path
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root, overrides = _write_source_maps(tmp_path)
    overrides.update(kwargs.pop("required_input_overrides", {}) if "required_input_overrides" in kwargs else {})
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
        **kwargs,
    )


def test_canonical_mutation_package_passes_report_only_current_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["package_decision"] == plan.PACKAGE_DECISION
    assert summary["registry_write_candidate_count"] == 14
    assert summary["trial_status_append_candidate_count"] == 22
    assert summary["exclusion_candidate_count"] == 5
    assert summary["append_only_mutation_command_approved"] is False
    assert summary["canonical_mutation_executed"] is False
    assert summary["registry_mutation_executed"] is False
    assert summary["trial_status_mutation_executed"] is False
    assert summary["experiment_ledger_mutation_executed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    package = report["canonical_mutation_package"]
    assert len(package["registry_note_candidates"]) == 14
    assert len(package["trial_status_append_candidates"]) == 22
    assert len(package["exclusion_disposition_candidates"]) == 5
    assert package["experiment_ledger_append_candidates"] == []
    assert package["canonical_write_allowed_by_this_report"] is False


def test_missing_source_map_fails_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)
    (tmp_path / overrides["unresolved_disposition"]).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("source maps" in failure.lower() for failure in report["failures"])


def test_candidate_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)
    payload = _read_json(tmp_path, overrides["append_decision"])
    draft = payload["draft_only_mutation_payload"]
    assert isinstance(draft, dict)
    rows = draft["trial_status_append_candidates"]
    assert isinstance(rows, list)
    draft["trial_status_append_candidates"] = rows[:-1]
    _write_json(tmp_path, overrides["append_decision"], payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("candidate counts drifted" in failure.lower() for failure in report["failures"])


def test_malformed_trial_status_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)
    (tmp_path / plan.TARGET_TRIAL_STATUSES).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_duplicate_proposed_trial_status_append_ids_fail_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)
    payload = _read_json(tmp_path, overrides["append_decision"])
    draft = payload["draft_only_mutation_payload"]
    assert isinstance(draft, dict)
    rows = draft["trial_status_append_candidates"]
    assert isinstance(rows, list)
    assert len(rows) >= 2
    rows[1]["trial_id"] = rows[0]["trial_id"]  # type: ignore[index]
    _write_json(tmp_path, overrides["append_decision"], payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("duplicate" in failure.lower() for failure in report["failures"])


def test_source_map_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)
    payload = _read_json(tmp_path, overrides["append_decision"])
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["promotion_allowed"] = True
    _write_json(tmp_path, overrides["append_decision"], payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("upgraded" in failure.lower() for failure in report["failures"])


def test_write_approval_fails_closed(tmp_path: Path) -> None:
    reports_root, overrides = _write_source_maps(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
        approval_overrides={"canonical_mutation_executed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path, monkeypatch: object) -> None:
    _write_source_maps(tmp_path)
    monkeypatch.setitem(plan.REQUIRED_INPUTS, "unresolved_disposition", SHORT_PACKAGE_INPUTS["unresolved_disposition"])
    monkeypatch.setitem(plan.REQUIRED_INPUTS, "append_decision", SHORT_PACKAGE_INPUTS["append_decision"])
    reports_root = tmp_path / "reports" / "master_audit" / "canonical_package"

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            "reports/master_audit/canonical_package",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["registry_write_candidate_count"] == 14
    assert payload["summary"]["trial_status_append_candidate_count"] == 22
    assert payload["summary"]["exclusion_candidate_count"] == 5
    assert payload["summary"]["canonical_mutation_executed"] is False
