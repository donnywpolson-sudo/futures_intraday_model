from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    apply_master_audit_canonical_trial_search_append_only_mutation_package as apply_plan,
)
from scripts.validation import (
    build_master_audit_canonical_trial_search_append_only_mutation_package as package_plan,
)
from tests.validation import (
    test_build_master_audit_canonical_trial_search_append_only_mutation_package as package_fixture,
)


def _write_package(tmp_path: Path) -> Path:
    reports_root, overrides = package_fixture._write_source_maps(tmp_path)
    report = package_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )
    package_plan.write_report(report, reports_root)
    return reports_root / package_plan.REPORT_JSON


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _trial_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_dry_run_writes_receipt_without_canonical_mutation(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)
    registry = tmp_path / apply_plan.TARGET_REGISTRY
    trials = tmp_path / apply_plan.TARGET_TRIAL_STATUSES
    before_registry = registry.read_text(encoding="utf-8")
    before_trials = trials.read_text(encoding="utf-8")

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=tmp_path / "reports/master_audit/receipt",
        execute=False,
        approval_token=None,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == apply_plan.DRY_RUN_STATUS
    assert report["summary"]["canonical_mutation_executed"] is False
    assert registry.read_text(encoding="utf-8") == before_registry
    assert trials.read_text(encoding="utf-8") == before_trials


def test_execute_appends_registry_notes_and_trial_status_rows(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)
    receipt_root = tmp_path / "reports/master_audit/receipt"

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=receipt_root,
        execute=True,
        approval_token=apply_plan.APPROVAL_TOKEN,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == apply_plan.PASS_STATUS
    summary = report["summary"]
    assert summary["append_only_mutation_command_approved"] is True
    assert summary["canonical_mutation_executed"] is True
    assert summary["registry_note_append_count"] == 14
    assert summary["trial_status_append_count"] == 22
    assert summary["experiment_ledger_append_count"] == 0
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    registry = _read_json(tmp_path / apply_plan.TARGET_REGISTRY)
    notes = []
    statuses_before = {
        row["target_hypothesis_id"]: row["status"]
        for row in registry["hypotheses"]  # type: ignore[index]
        if isinstance(row, dict)
    }
    for row in registry["hypotheses"]:  # type: ignore[index]
        if isinstance(row, dict):
            notes.extend(row.get("master_audit_disposition_notes", []))
            assert statuses_before[row["target_hypothesis_id"]] == row["status"]
    assert len(notes) == 14
    trials = _trial_rows(tmp_path / apply_plan.TARGET_TRIAL_STATUSES)
    assert len(trials) == 44
    appended = [
        row
        for row in trials
        if row.get("stage") == "master_audit_family_metadata_append_only_disposition"
    ]
    assert len(appended) == 22


def test_execute_requires_exact_approval_token(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=tmp_path / "reports/master_audit/receipt",
        execute=True,
        approval_token="wrong",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == apply_plan.FAIL_STATUS
    assert any("approval token" in failure.lower() for failure in report["failures"])
    assert len(_trial_rows(tmp_path / apply_plan.TARGET_TRIAL_STATUSES)) == 22


def test_dirty_canonical_file_fails_closed(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=tmp_path / "reports/master_audit/receipt",
        execute=True,
        approval_token=apply_plan.APPROVAL_TOKEN,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[" M manifests/target_hypotheses/registry.json"],
    )

    assert report["status"] == apply_plan.FAIL_STATUS
    assert any("already dirty" in failure.lower() for failure in report["failures"])


def test_trial_id_collision_fails_closed(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)
    package = _read_json(package_path)
    existing_trial_id = _trial_rows(tmp_path / apply_plan.TARGET_TRIAL_STATUSES)[0]["trial_id"]
    first = package["canonical_mutation_package"]["trial_status_append_candidates"][0]  # type: ignore[index]
    first["trial_id"] = existing_trial_id  # type: ignore[index]
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=tmp_path / "reports/master_audit/receipt",
        execute=True,
        approval_token=apply_plan.APPROVAL_TOKEN,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == apply_plan.FAIL_STATUS
    assert any("collide" in failure.lower() for failure in report["failures"])


def test_package_readiness_upgrade_fails_closed(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)
    package = _read_json(package_path)
    package["summary"]["promotion_allowed"] = True  # type: ignore[index]
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=tmp_path / "reports/master_audit/receipt",
        execute=True,
        approval_token=apply_plan.APPROVAL_TOKEN,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == apply_plan.FAIL_STATUS
    assert any("upgrades readiness" in failure.lower() for failure in report["failures"])


def test_main_writes_receipt_pair_and_applies_mutation(tmp_path: Path) -> None:
    package_path = _write_package(tmp_path)
    receipt_root = tmp_path / "reports/master_audit/receipt"

    exit_code = apply_plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--package",
            str(package_path),
            "--receipt-root",
            "reports/master_audit/receipt",
            "--execute-append-only-mutation",
            "--approval-token",
            apply_plan.APPROVAL_TOKEN,
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in receipt_root.iterdir()) == [
        apply_plan.RECEIPT_JSON,
        apply_plan.RECEIPT_MD,
    ]
    receipt = _read_json(receipt_root / apply_plan.RECEIPT_JSON)
    assert receipt["summary"]["canonical_mutation_executed"] is True
    assert len(_trial_rows(tmp_path / apply_plan.TARGET_TRIAL_STATUSES)) == 44
