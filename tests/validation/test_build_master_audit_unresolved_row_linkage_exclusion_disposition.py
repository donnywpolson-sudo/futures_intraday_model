from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_trial_search_append_only_disposition_mutation_decision as append_plan,
)
from scripts.validation import (
    build_master_audit_unresolved_row_linkage_exclusion_disposition as plan,
)
from tests.validation import (
    test_build_master_audit_trial_search_append_only_disposition_mutation_decision as append_fixture,
)


SHORT_APPEND_ROOT = Path("reports/master_audit/append_decision")
SHORT_APPEND_DECISION = SHORT_APPEND_ROOT / append_plan.REPORT_JSON


def _write_append_decision_report(tmp_path: Path) -> Path:
    append_fixture._write_upstream_report(tmp_path)
    for line in (tmp_path / plan.EXPERIMENT_LEDGER).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        audit_path = tmp_path / str(row["audit_report_path"])
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    reports_root = tmp_path / SHORT_APPEND_ROOT
    report = append_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    reports_root.mkdir(parents=True, exist_ok=True)
    append_plan.write_report(report, reports_root)
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _read_json(tmp_path: Path, relative_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))


def _write_json(tmp_path: Path, relative_path: Path, payload: dict[str, object]) -> None:
    path = tmp_path / relative_path
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _write_append_decision_report(tmp_path)
    overrides = {"append_decision": SHORT_APPEND_DECISION}
    overrides.update(kwargs.pop("required_input_overrides", {}) if "required_input_overrides" in kwargs else {})
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
        **kwargs,
    )


def test_unresolved_row_linkage_exclusion_passes_current_blocked_state(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["unresolved_row_count"] == 5
    assert summary["legacy_experiment_ledger_row_count"] == 4
    assert summary["current_wfa_phase8_statistical_row_count"] == 1
    assert summary["linkable_row_count"] == 0
    assert summary["exclusion_candidate_count"] == 5
    assert summary["disposition"] == plan.DISPOSITION
    assert summary["canonical_append_only_mutation_allowed"] is False
    assert summary["registry_mutation_allowed"] is False
    assert summary["trial_status_mutation_allowed"] is False
    assert summary["experiment_ledger_mutation_allowed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    rows = report["unresolved_row_exclusion_dispositions"]
    assert len(rows) == 5
    assert all(row["disposition"] == plan.DISPOSITION for row in rows)
    assert all(row["linkable_to_target_hypothesis"] is False for row in rows)
    assert all(row["canonical_mutation_allowed"] is False for row in rows)


def test_missing_append_decision_report_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
    (tmp_path / SHORT_APPEND_DECISION).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("append-only disposition decision" in failure.lower() for failure in report["failures"])


def test_unresolved_row_count_drift_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
    payload = _read_json(tmp_path, SHORT_APPEND_DECISION)
    draft = payload["draft_only_mutation_payload"]
    assert isinstance(draft, dict)
    rows = draft["blocked_unresolved_rows"]
    assert isinstance(rows, list)
    draft["blocked_unresolved_rows"] = rows[:-1]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["unresolved_family_metadata_row_count"] = 4
    _write_json(tmp_path, SHORT_APPEND_DECISION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("unresolved-row count drifted" in failure.lower() for failure in report["failures"])


def test_missing_legacy_evidence_path_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
    payload = _read_json(tmp_path, SHORT_APPEND_DECISION)
    draft = payload["draft_only_mutation_payload"]
    assert isinstance(draft, dict)
    rows = draft["blocked_unresolved_rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    hypothesis = first["hypothesis_id"]
    assert isinstance(hypothesis, dict)
    evidence_paths = hypothesis["evidence_paths"]
    assert isinstance(evidence_paths, list)
    (tmp_path / str(evidence_paths[0])).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("source evidence paths are missing" in failure.lower() for failure in report["failures"])


def test_accidental_primary_hypothesis_linkage_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
    payload = _read_json(tmp_path, SHORT_APPEND_DECISION)
    draft = payload["draft_only_mutation_payload"]
    assert isinstance(draft, dict)
    rows = draft["blocked_unresolved_rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["hypothesis_id"] = "h00"
    _write_json(tmp_path, SHORT_APPEND_DECISION, payload)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("became linkable" in failure.lower() for failure in report["failures"])


def test_malformed_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
    (tmp_path / plan.EXPERIMENT_LEDGER).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_write_approval_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
        approval_overrides={"canonical_append_only_mutation_allowed": True},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("write approval" in failure.lower() for failure in report["failures"])


def test_upstream_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_append_decision_report(tmp_path)
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
        required_input_overrides={"append_decision": SHORT_APPEND_DECISION},
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("upstream" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path, monkeypatch: object) -> None:
    _write_append_decision_report(tmp_path)
    reports_root = tmp_path / "reports" / "master_audit" / "row_linkage_exclusion"
    monkeypatch.setitem(plan.REQUIRED_INPUTS, "append_decision", SHORT_APPEND_DECISION)

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            "reports/master_audit/row_linkage_exclusion",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["linkable_row_count"] == 0
    assert payload["summary"]["exclusion_candidate_count"] == 5
    assert payload["summary"]["promotion_allowed"] is False
