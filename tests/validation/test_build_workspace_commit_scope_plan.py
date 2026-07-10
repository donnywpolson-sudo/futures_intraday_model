from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_workspace_commit_scope_plan as scope_plan


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _closeout_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "closeout_classification": "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY",
            "full_master_audit_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
        },
    }


def _base_repo(tmp_path: Path, *, closeout_payload: dict[str, object] | None = None) -> Path:
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "outline\n")
    _write_text(tmp_path / "MASTER_AUDIT.md", "audit\n")
    _write_json(
        tmp_path / scope_plan.REQUIRED_INPUTS["master_audit_closeout"],
        closeout_payload or _closeout_payload(),
    )
    return tmp_path / scope_plan.DEFAULT_REPORTS_ROOT


def _status_lines() -> list[str]:
    return [
        " M CODEX_HANDOFF.md",
        "?? MASTER_AUDIT.md",
        "?? scripts/validation/build_workspace_commit_scope_plan.py",
        "?? tests/validation/test_build_workspace_commit_scope_plan.py",
        "?? reports/master_audit/master_audit_closeout_20260709/master_audit_closeout.json",
        " M configs/models.yaml",
        "?? scripts/prop_account_simulation/",
        "?? scripts/phase5_wfa/build_hardened_wfa_splits.py",
        "?? scripts/validation/audit_wfa_split_contamination.py",
        "?? scripts/validation/build_execution_realism_primary_evidence_intake.py",
        " M scripts/export_live_shadow_bundle.py",
        "?? docs/phase2_causal_session_normalization_spec.md",
        " M scripts/phase2_causal_base/build_causal_base_data.py",
        " M scripts/validation/model_registry.py",
    ]


def _build(
    tmp_path: Path,
    *,
    git_status_lines: list[str] | None = None,
    closeout_payload: dict[str, object] | None = None,
    reports_root: Path | None = None,
) -> dict[str, object]:
    root = _base_repo(tmp_path, closeout_payload=closeout_payload)
    return scope_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root or root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=git_status_lines if git_status_lines is not None else _status_lines(),
    )


def test_commit_scope_plan_passes_and_classifies_each_status_entry_once(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == scope_plan.PASS_STATUS
    assert report["summary"]["git_status_entry_count"] == len(_status_lines())
    assert report["summary"]["classified_entry_count"] == len(_status_lines())
    assert report["summary"]["auto_stage_allowed_count"] == 0
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["final_holdout_ready"] is False
    paths = [entry["path"] for entry in report["classified_entries"]]
    assert len(paths) == len(set(paths))
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_commit_scope_buckets_include_expected_groups(tmp_path: Path) -> None:
    report = _build(tmp_path)

    buckets = {entry["path"]: entry["bucket"] for entry in report["classified_entries"]}
    assert buckets["CODEX_HANDOFF.md"] == "coordination_docs"
    assert buckets["configs/models.yaml"] == "config_changes"
    assert buckets["scripts/prop_account_simulation/"] == "prop_account_simulation"
    assert buckets["scripts/phase5_wfa/build_hardened_wfa_splits.py"] == "hardened_split_decision_work"
    assert buckets["scripts/export_live_shadow_bundle.py"] == "live_shadow_export_work"
    assert buckets["scripts/validation/build_workspace_commit_scope_plan.py"] == (
        "workspace_or_master_audit_closeout_scope"
    )


def test_manual_unclassified_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, git_status_lines=["?? mystery/path.txt"])

    assert report["status"] == scope_plan.FAIL_STATUS
    assert any("manual-review-only unclassified" in failure for failure in report["failures"])


def test_duplicate_status_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, git_status_lines=[" M CODEX_HANDOFF.md", " M CODEX_HANDOFF.md"])

    assert report["status"] == scope_plan.FAIL_STATUS
    assert any("duplicate path classifications" in failure for failure in report["failures"])


def test_closeout_upgrade_fails_closed(tmp_path: Path) -> None:
    bad_closeout = _closeout_payload()
    bad_closeout["summary"]["promotion_allowed"] = True

    report = _build(tmp_path, closeout_payload=bad_closeout)

    assert report["status"] == scope_plan.FAIL_STATUS
    assert any("promotion_allowed" in failure for failure in report["failures"])


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, reports_root=tmp_path / "data" / "bad")

    assert report["status"] == scope_plan.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])


def test_write_report_outputs_only_json_and_markdown(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    report = scope_plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=_status_lines(),
    )

    json_path, md_path = scope_plan.write_report(report, reports_root)

    assert json_path.name == scope_plan.REPORT_JSON
    assert md_path.name == scope_plan.REPORT_MD
    assert sorted(path.name for path in reports_root.iterdir()) == [
        scope_plan.REPORT_JSON,
        scope_plan.REPORT_MD,
    ]
