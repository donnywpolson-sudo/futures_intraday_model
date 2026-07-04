from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_plan as readiness_plan
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_review as review_fixtures


def _conversion_ignored_paths(tmp_path: Path, reports_root: Path) -> list[str]:
    return review_fixtures.plan_fixtures._ignored_paths(
        tmp_path,
        reports_root,
        include_candidate_outputs=True,
    )


def _expected_output_paths(tmp_path: Path) -> list[str]:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    return sorted(
        [
            (reports_root / "ES_2026_candidate_raw_quality_drilldown.json").relative_to(tmp_path).as_posix(),
            (reports_root / "candidate_raw_alignment" / "include_ES_2026.json").relative_to(tmp_path).as_posix(),
            (reports_root / "candidate_raw_alignment" / "ES_2026_candidate_raw_dbn_alignment.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_alignment" / "ES_2026_candidate_raw_dbn_alignment.md")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_readiness" / "include_ES_2026.json").relative_to(tmp_path).as_posix(),
            (reports_root / "candidate_readiness" / "phase2_readiness_summary.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_readiness" / "phase2_readiness_summary.md").relative_to(tmp_path).as_posix(),
            (reports_root / "candidate_readiness" / "phase2_readiness.progress.jsonl")
            .relative_to(tmp_path)
            .as_posix(),
        ]
    )


def _ignored_paths(
    tmp_path: Path,
    reports_root: Path,
    *,
    include_readiness_outputs: bool = True,
) -> list[str]:
    paths = _conversion_ignored_paths(tmp_path, reports_root)
    if include_readiness_outputs:
        paths.extend(_expected_output_paths(tmp_path))
    return sorted(set(paths))


def _build(
    tmp_path: Path,
    *,
    write_plans: bool = True,
    write_archives: bool = True,
    write_outputs: bool = False,
    staged: list[str] | None = None,
    include_expected_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        review_fixtures._setup(
            tmp_path,
            write_plans=write_plans,
            write_archives=write_archives,
        )
    )
    if write_outputs:
        review_fixtures._write_conversion_outputs(
            candidate_raw_root=candidate_raw_root,
            repair_reports_root=repair_reports_root,
        )
    return readiness_plan.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=repair_reports_root / "candidate_raw_alignment" / "ES_2026_candidate_raw_dbn_alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else _ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=include_expected_outputs_in_ignored,
        ),
    )


def test_missing_conversion_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == readiness_plan.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert any(
        check["name"] == "candidate_conversion_review_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_valid_conversion_outputs_build_readiness_plan(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=True)

    assert report["summary"]["status"] == readiness_plan.STATUS_READY
    assert report["summary"]["command_family_count"] == 3
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert {family["name"] for family in report["command_families"]} == {
        "candidate_raw_quality_drilldown",
        "candidate_raw_dbn_alignment_audit",
        "candidate_readiness_only_rerun_after_repair",
    }
    readiness_command = next(
        family["command"]
        for family in report["command_families"]
        if family["name"] == "candidate_readiness_only_rerun_after_repair"
    )
    expected_alignment = (
        tmp_path
        / "reports"
        / "pipeline_audit"
        / "repair_plan_v1"
        / "candidate_raw_alignment"
        / "ES_2026_candidate_raw_dbn_alignment.json"
    ).as_posix()
    assert f"--raw-alignment-report {expected_alignment}" in readiness_command
    assert readiness_command.count(expected_alignment) == 1
    assert f"{tmp_path.as_posix()}/{expected_alignment}" not in readiness_command
    alignment = next(
        family
        for family in report["command_families"]
        if family["name"] == "candidate_raw_dbn_alignment_audit"
    )
    assert "--market-year-include-list" in alignment["command"]
    assert alignment["pre_run_artifacts"][0]["content"] == {
        "market_years": [{"market": "ES", "year": 2026}]
    }


def test_filters_windows_style_ignored_readiness_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    ignored_paths = [
        path.replace("/", "\\")
        for path in _ignored_paths(tmp_path, reports_root, include_readiness_outputs=True)
    ]
    ignored_paths.append("reports\\pipeline_audit\\future.json")

    report = _build(
        tmp_path,
        write_outputs=True,
        ignored_paths=sorted(ignored_paths),
    )

    assert report["summary"]["status"] == readiness_plan.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["unignored_expected_generated_output_count"] == 0


def test_unignored_candidate_readiness_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        write_outputs=True,
        include_expected_outputs_in_ignored=False,
    )

    assert report["summary"]["status"] == readiness_plan.STATUS_NO_GO
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["unignored_expected_generated_output_count"] == 8
    assert any(
        check["name"] == "candidate_readiness_expected_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=True, staged=["reports/generated.json"])

    assert report["summary"]["status"] == readiness_plan.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_outputs_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        review_fixtures._setup(tmp_path)
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = readiness_plan.main(
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
    assert f"{readiness_plan.STAGE} status={readiness_plan.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
