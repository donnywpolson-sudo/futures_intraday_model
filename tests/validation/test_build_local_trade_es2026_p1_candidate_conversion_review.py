from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_review as review
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_plan as plan_fixtures
from tests.validation import test_build_local_trade_es2026_p1_repair_plan as repair_fixtures


def _setup(
    tmp_path: Path,
    *,
    write_plans: bool = True,
    write_archives: bool = True,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    work_order, drilldown, checkpoint = repair_fixtures._write_reports(tmp_path)
    repair_reports_root = (
        plan_fixtures._write_plans(tmp_path)
        if write_plans
        else tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    )
    if write_archives:
        for schema in ("statistics", "status"):
            plan_fixtures._write_archive_and_manifest(tmp_path, schema)
    candidate_raw_root = tmp_path / "data" / "raw_es2026_candidate"
    output_root = tmp_path / "data" / "causal_es2026_candidate"
    raw_alignment_report = repair_reports_root / "alignment.json"
    return work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report


def _write_conversion_outputs(
    *,
    candidate_raw_root: Path,
    repair_reports_root: Path,
    audit_status: str = "PASS",
    status_readiness: str = "PASS",
    statistics_readiness: str = "PASS",
) -> None:
    parquet_path = candidate_raw_root / "ES" / "2026.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.write_bytes(b"candidate parquet")
    conversion_root = repair_reports_root / "candidate_raw_conversion"
    conversion_root.mkdir(parents=True, exist_ok=True)
    for name in (
        "databento_convert_results.json",
        "raw_ingest_manifest.json",
        "raw_parquet_manifest.json",
    ):
        (conversion_root / name).write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    audit_root = repair_reports_root / "candidate_raw_optional_schema_audit"
    audit_root.mkdir(parents=True, exist_ok=True)
    (audit_root / "ES_2026_optional_schema_audit.json").write_text(
        json.dumps(
            {
                "stage": "raw_enriched_optional_schema_audit",
                "status": audit_status,
                "raw_root": candidate_raw_root.as_posix(),
                "file_count": 1,
                "verdicts": {
                    "optional_status_readiness": status_readiness,
                    "optional_statistics_readiness": statistics_readiness,
                },
            }
        ),
        encoding="utf-8",
    )
    (audit_root / "ES_2026_optional_schema_audit.md").write_text(f"# {audit_status}\n", encoding="utf-8")


def _build(
    tmp_path: Path,
    *,
    write_plans: bool = True,
    write_archives: bool = True,
    write_outputs: bool = False,
    audit_status: str = "PASS",
    staged: list[str] | None = None,
    include_candidate_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path,
        write_plans=write_plans,
        write_archives=write_archives,
    )
    if write_outputs:
        _write_conversion_outputs(
            candidate_raw_root=candidate_raw_root,
            repair_reports_root=repair_reports_root,
            audit_status=audit_status,
            status_readiness="PASS" if audit_status == "PASS" else "FAIL",
        )
    return review.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_candidate_outputs=include_candidate_outputs_in_ignored,
        ),
    )


def test_missing_conversion_prerequisites_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_plans=False, write_archives=False)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert any(
        check["name"] == "candidate_conversion_plan_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_conversion_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["expected_candidate_output_count"] == 6
    assert any(
        check["name"] == "candidate_conversion_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_valid_conversion_outputs_are_review_ready(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=True)

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["expected_candidate_output_count"] == 6
    assert report["summary"]["ignored_expected_candidate_output_count"] == 6
    assert report["summary"]["unignored_expected_candidate_output_count"] == 0
    assert report["summary"]["next_command_family_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert {family["name"] for family in report["next_command_families"]} == {
        "candidate_raw_quality_drilldown",
        "candidate_readiness_only_rerun_after_repair",
    }


def test_filters_windows_style_ignored_candidate_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    ignored_paths = [
        path.replace("/", "\\")
        for path in plan_fixtures._ignored_paths(tmp_path, reports_root, include_candidate_outputs=True)
    ]
    ignored_paths.append("reports\\pipeline_audit\\future.json")

    report = _build(
        tmp_path,
        write_outputs=True,
        ignored_paths=sorted(ignored_paths),
    )

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["expected_candidate_output_count"] == 6
    assert report["summary"]["ignored_expected_candidate_output_count"] == 6
    assert report["summary"]["unignored_expected_candidate_output_count"] == 0


def test_unignored_candidate_outputs_fail_closed(tmp_path: Path, monkeypatch) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path,
        write_plans=True,
        write_archives=True,
    )
    _write_conversion_outputs(
        candidate_raw_root=candidate_raw_root,
        repair_reports_root=repair_reports_root,
    )
    full_ignored_paths = plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_candidate_outputs=True,
    )
    plan_only_ignored_paths = plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_candidate_outputs=False,
    )
    original_plan_build_report = review.conversion_plan.build_report

    def ready_plan_build_report(**kwargs):
        kwargs["ignored_generated_paths"] = full_ignored_paths
        return original_plan_build_report(**kwargs)

    monkeypatch.setattr(review.conversion_plan, "build_report", ready_plan_build_report)
    report = review.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=plan_only_ignored_paths,
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["unignored_expected_candidate_output_count"] == 6
    assert any(
        check["name"] == "candidate_conversion_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_failed_optional_audit_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=True, audit_status="FAIL")

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert "optional schema audit status is not PASS: 'FAIL'" in next(
        check["observed"]
        for check in report["checks"]
        if check["name"] == "candidate_conversion_outputs_valid"
    )


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=True, staged=["reports/generated.json"])

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_outputs_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = review.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(work_order),
            "--drilldown-report",
            str(drilldown),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--repair-reports-root",
            str(repair_reports_root),
            "--candidate-raw-root",
            str(candidate_raw_root),
            "--output-root",
            str(output_root),
            "--raw-alignment-report",
            str(raw_alignment_report),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{review.STAGE} status={review.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
