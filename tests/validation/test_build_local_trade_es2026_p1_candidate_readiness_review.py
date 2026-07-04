from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_candidate_readiness_review as review
from tests.validation import test_run_local_trade_es2026_p1_candidate_readiness as runner_fixtures


def _write_readiness_outputs(
    *,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    raw_alignment_report: Path,
    readiness_status: str = "PASS",
) -> None:
    raw_quality = repair_reports_root / "ES_2026_candidate_raw_quality_drilldown.json"
    raw_quality.parent.mkdir(parents=True, exist_ok=True)
    raw_quality.write_text(
        json.dumps(
            {
                "stage": "phase2_readiness_raw_drilldown",
                "status": "PASS",
                "selected_market_year_count": 1,
                "selected_market_years": [{"market": "ES", "year": 2026}],
            }
        ),
        encoding="utf-8",
    )
    alignment_include = repair_reports_root / "candidate_raw_alignment" / "include_ES_2026.json"
    alignment_include.parent.mkdir(parents=True, exist_ok=True)
    alignment_include.write_text(json.dumps({"market_years": [{"market": "ES", "year": 2026}]}), encoding="utf-8")
    raw_alignment_report.parent.mkdir(parents=True, exist_ok=True)
    raw_alignment_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "raw_root": candidate_raw_root.as_posix(),
                "market_year_include_list_applied": True,
            }
        ),
        encoding="utf-8",
    )
    raw_alignment_report.with_suffix(".md").write_text("# alignment\n", encoding="utf-8")
    readiness_root = repair_reports_root / "candidate_readiness"
    readiness_root.mkdir(parents=True, exist_ok=True)
    (readiness_root / "include_ES_2026.json").write_text(
        json.dumps({"market_years": [{"market": "ES", "year": 2026}]}),
        encoding="utf-8",
    )
    (readiness_root / "phase2_readiness_summary.json").write_text(
        json.dumps({"status": readiness_status, "selected_market_year_count": 1}),
        encoding="utf-8",
    )
    (readiness_root / "phase2_readiness_summary.md").write_text("# readiness\n", encoding="utf-8")
    (readiness_root / "phase2_readiness.progress.jsonl").write_text('{"stage":"done"}\n', encoding="utf-8")


def _build(
    tmp_path: Path,
    *,
    write_candidate_outputs: bool = True,
    write_readiness_outputs: bool = False,
    readiness_status: str = "PASS",
    staged: list[str] | None = None,
    include_readiness_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        runner_fixtures._setup(tmp_path, write_outputs=write_candidate_outputs)
    )
    if write_readiness_outputs:
        _write_readiness_outputs(
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            raw_alignment_report=raw_alignment_report,
            readiness_status=readiness_status,
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
        else runner_fixtures.plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_readiness_outputs=include_readiness_outputs_in_ignored,
        ),
    )


def test_missing_candidate_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_candidate_outputs=False)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["causal_base_repair_approved"] is False
    assert any(
        check["name"] == "candidate_readiness_plan_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_readiness_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["expected_readiness_output_count"] == 8
    assert any(
        check["name"] == "candidate_readiness_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_pass_readiness_outputs_are_review_ready(tmp_path: Path) -> None:
    report = _build(tmp_path, write_readiness_outputs=True)

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["expected_readiness_output_count"] == 8
    assert report["summary"]["ignored_expected_readiness_output_count"] == 8
    assert report["summary"]["unignored_expected_readiness_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["label_build_approved"] is False
    assert report["review_detail"]["readiness_status"] == "PASS"
    assert report["review_detail"]["raw_alignment_status"] == "PASS"


def test_filters_windows_style_ignored_readiness_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    ignored_paths = [
        path.replace("/", "\\")
        for path in runner_fixtures.plan_fixtures._ignored_paths(
            tmp_path,
            reports_root,
            include_readiness_outputs=True,
        )
    ]
    ignored_paths.append("reports\\pipeline_audit\\future.json")

    report = _build(
        tmp_path,
        write_readiness_outputs=True,
        ignored_paths=sorted(ignored_paths),
    )

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["expected_readiness_output_count"] == 8
    assert report["summary"]["ignored_expected_readiness_output_count"] == 8
    assert report["summary"]["unignored_expected_readiness_output_count"] == 0


def test_unignored_readiness_outputs_fail_closed(tmp_path: Path, monkeypatch) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        runner_fixtures._setup(tmp_path, write_outputs=True)
    )
    _write_readiness_outputs(
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        raw_alignment_report=raw_alignment_report,
    )
    full_ignored_paths = runner_fixtures.plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    )
    conversion_only_ignored_paths = runner_fixtures.plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=False,
    )
    original_plan_build_report = review.plan_gate.build_report

    def ready_plan_build_report(**kwargs):
        kwargs["ignored_generated_paths"] = full_ignored_paths
        return original_plan_build_report(**kwargs)

    monkeypatch.setattr(review.plan_gate, "build_report", ready_plan_build_report)
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
        ignored_generated_paths=conversion_only_ignored_paths,
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["unignored_expected_readiness_output_count"] == 8
    assert any(
        check["name"] == "candidate_readiness_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_failed_readiness_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_readiness_outputs=True, readiness_status="FAIL")

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert "candidate readiness status is not PASS: 'FAIL'" in next(
        check["observed"]
        for check in report["checks"]
        if check["name"] == "candidate_readiness_outputs_valid"
    )


def test_cli_no_go_writes_no_reports_when_outputs_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        runner_fixtures._setup(tmp_path)
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
