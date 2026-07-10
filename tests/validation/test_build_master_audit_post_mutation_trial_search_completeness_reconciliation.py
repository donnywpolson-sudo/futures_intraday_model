from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import (
    apply_master_audit_canonical_trial_search_append_only_mutation_package as apply_plan,
)
from scripts.validation import (
    build_master_audit_post_mutation_trial_search_completeness_reconciliation as plan,
)
from tests.validation import (
    test_apply_master_audit_canonical_trial_search_append_only_mutation_package as apply_fixture,
)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_post_mutation_state(tmp_path: Path) -> dict[str, Path]:
    package_path = apply_fixture._write_package(tmp_path)
    receipt_root = tmp_path / "reports/master_audit/mutation_receipt"
    receipt = apply_plan.build_receipt(
        repo_root=tmp_path,
        package_path=package_path,
        receipt_root=receipt_root,
        execute=True,
        approval_token=apply_plan.APPROVAL_TOKEN,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )
    apply_plan.write_receipt(receipt, receipt_root)
    _normalize_family_metadata_fixture(tmp_path / plan.TARGET_TRIAL_STATUSES)
    _normalize_blocking_evidence_fixture(tmp_path)
    receipt_path = receipt_root / apply_plan.RECEIPT_JSON
    return {"mutation_receipt": receipt_path.relative_to(tmp_path)}


def _normalize_family_metadata_fixture(trials_path: Path) -> None:
    rows = [json.loads(line) for line in trials_path.read_text(encoding="utf-8").splitlines()]
    family_index = 0
    for row in rows:
        if row.get("stage") != "master_audit_family_metadata_append_only_disposition":
            continue
        row["search_family_id"] = f"search_family::{family_index % 10:02d}"
        row["multiple_testing_family_id"] = f"multiple_testing_family::{family_index % 2:02d}"
        family_index += 1
    trials_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def _normalize_blocking_evidence_fixture(tmp_path: Path) -> None:
    statistical_path = tmp_path / plan.STATISTICAL_SUMMARY
    statistical = _read_json(statistical_path)
    statistical["failure_count"] = 5
    statistical["statistical_validity_ready"] = False
    required = statistical.setdefault("required_checks", {})
    assert isinstance(required, dict)
    required["pbo"] = {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None}
    required["deflated_sharpe"] = {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None}
    required["multiple_testing_adjustment"] = {
        "status": "FAIL_MISSING_TRIAL_LOG",
        "trial_count": None,
    }
    required["probabilistic_sharpe"] = {"status": "FAIL"}
    required["regime_breakdowns"] = {"status": "FAIL"}
    _write_json(statistical_path, statistical)

    matrix_path = tmp_path / plan.ALPHA_MATRIX
    matrix = _read_json(matrix_path)
    matrix["alpha_evidence_ready"] = False
    _write_json(matrix_path, matrix)

    closeout_path = tmp_path / plan.ALPHA_CLOSEOUT
    closeout = _read_json(closeout_path)
    closeout["verdict"] = "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
    closeout["future_modeling_allowed"] = False
    closeout["promotion_allowed"] = False
    _write_json(closeout_path, closeout)

    run_status_path = tmp_path / plan.RUN_STATUS
    run_status = _read_json(run_status_path)
    summary = run_status.setdefault("summary", {})
    assert isinstance(summary, dict)
    summary["data_model_commands_executed"] = False
    summary["wfa_modeling_executed"] = False
    summary["predictions_executed"] = False
    summary["provider_network_calls_executed"] = False
    summary["promotion_or_freeze_or_holdout_executed"] = False
    summary["paper_or_live_executed"] = False
    _write_json(run_status_path, run_status)


def _build_with_overrides(tmp_path: Path, overrides: dict[str, Path]) -> dict[str, object]:
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/post_mutation",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    overrides = _write_post_mutation_state(tmp_path)
    overrides.update(kwargs.pop("required_input_overrides", {}) if "required_input_overrides" in kwargs else {})
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/post_mutation",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
        **kwargs,
    )


def test_post_mutation_completeness_passes_current_state(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    summary = report["summary"]
    assert summary["trial_ledger_search_path_complete"] is True
    assert summary["pbo_status"] == plan.READY_STATUS
    assert summary["deflated_sharpe_status"] == plan.READY_STATUS
    assert summary["multiple_testing_status"] == plan.READY_STATUS
    assert summary["pbo_applicability_ready"] is True
    assert summary["deflated_sharpe_applicability_ready"] is True
    assert summary["multiple_testing_applicability_ready"] is True
    assert summary["separate_statistical_recompute_required"] is True
    assert summary["statistical_recompute_executed"] is False
    assert summary["statistical_validity_ready"] is False
    assert summary["model_trust_ready"] is False
    assert summary["promotion_allowed"] is False
    assert summary["registry_master_audit_note_count"] == 14
    assert summary["trial_status_row_count"] == 44
    assert summary["family_metadata_row_count"] == 22
    assert summary["search_family_count"] == 10
    assert summary["multiple_testing_family_count"] == 2
    assert summary["experiment_ledger_row_count"] == 4


def test_missing_mutation_receipt_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    (tmp_path / overrides["mutation_receipt"]).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "reports/master_audit/post_mutation",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
        required_input_overrides=overrides,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("mutation receipt" in failure.lower() for failure in report["failures"])


def test_missing_registry_notes_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    registry_path = tmp_path / plan.TARGET_REGISTRY
    registry = _read_json(registry_path)
    for row in registry["hypotheses"]:  # type: ignore[index]
        if isinstance(row, dict):
            row.pop("master_audit_disposition_notes", None)
    _write_json(registry_path, registry)

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("search metadata is incomplete" in failure.lower() for failure in report["failures"])


def test_missing_family_id_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    trials_path = tmp_path / plan.TARGET_TRIAL_STATUSES
    rows = [json.loads(line) for line in trials_path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row.get("stage") == "master_audit_family_metadata_append_only_disposition":
            row.pop("search_family_id", None)
            break
    trials_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("search metadata is incomplete" in failure.lower() for failure in report["failures"])


def test_duplicate_appended_trial_id_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    trials_path = tmp_path / plan.TARGET_TRIAL_STATUSES
    rows = [json.loads(line) for line in trials_path.read_text(encoding="utf-8").splitlines()]
    family_rows = [
        row for row in rows if row.get("stage") == "master_audit_family_metadata_append_only_disposition"
    ]
    family_rows[1]["trial_id"] = family_rows[0]["trial_id"]
    trials_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("search metadata is incomplete" in failure.lower() for failure in report["failures"])


def test_experiment_ledger_mutation_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    ledger_path = tmp_path / plan.EXPERIMENT_LEDGER
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"audit_report_path": "extra.json"}) + "\n")

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("experiment ledger" in failure.lower() for failure in report["failures"])


def test_statistical_summary_upgrade_fails_closed(tmp_path: Path) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    summary_path = tmp_path / plan.STATISTICAL_SUMMARY
    payload = _read_json(summary_path)
    payload["statistical_validity_ready"] = True
    _write_json(summary_path, payload)

    report = _build_with_overrides(tmp_path, overrides)

    assert report["status"] == plan.FAIL_STATUS
    assert any("statistical summary" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path, monkeypatch: object) -> None:
    overrides = _write_post_mutation_state(tmp_path)
    monkeypatch.setitem(plan.REQUIRED_INPUTS, "mutation_receipt", overrides["mutation_receipt"])
    reports_root = tmp_path / "reports/master_audit/post_mutation"

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            "reports/master_audit/post_mutation",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    report = _read_json(reports_root / plan.REPORT_JSON)
    assert report["summary"]["trial_ledger_search_path_complete"] is True
    assert report["summary"]["statistical_validity_ready"] is False
