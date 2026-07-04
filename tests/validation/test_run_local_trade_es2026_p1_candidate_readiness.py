from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.validation import run_local_trade_es2026_p1_candidate_readiness as runner
from tests.validation import test_build_local_trade_es2026_p1_candidate_readiness_plan as plan_fixtures
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_review as review_fixtures


def _arg_value(argv: Sequence[str], flag: str) -> str:
    index = list(argv).index(flag)
    return str(argv[index + 1])


def _setup(
    tmp_path: Path,
    *,
    write_outputs: bool = True,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, _ = (
        review_fixtures._setup(tmp_path)
    )
    if write_outputs:
        review_fixtures._write_conversion_outputs(
            candidate_raw_root=candidate_raw_root,
            repair_reports_root=repair_reports_root,
        )
    raw_alignment_report = repair_reports_root / "candidate_raw_alignment" / "ES_2026_candidate_raw_dbn_alignment.json"
    return work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report


def _expected_output_paths(
    tmp_path: Path,
    *,
    work_order: Path,
    drilldown: Path,
    checkpoint: Path,
    repair_reports_root: Path,
    candidate_raw_root: Path,
    output_root: Path,
    raw_alignment_report: Path,
) -> list[str]:
    return plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_readiness_outputs=True,
    )


def _build(
    tmp_path: Path,
    *,
    write_outputs: bool = True,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner=runner._default_command_runner,
    staged: list[str] | None = None,
    include_expected_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        _setup(tmp_path, write_outputs=write_outputs)
    )
    default_ignored_paths = (
        _expected_output_paths(
            tmp_path,
            work_order=work_order,
            drilldown=drilldown,
            checkpoint=checkpoint,
            repair_reports_root=repair_reports_root,
            candidate_raw_root=candidate_raw_root,
            output_root=output_root,
            raw_alignment_report=raw_alignment_report,
        )
        if include_expected_outputs_in_ignored
        else []
    )
    return runner.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
        execute=execute,
        approval_token=approval_token,
        command_runner=command_runner,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths if ignored_paths is not None else default_ignored_paths,
    )


def test_missing_candidate_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_outputs=False)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert any(
        check["name"] == "candidate_readiness_plan_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_ready_plan_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 3
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False


def test_filters_windows_style_ignored_planned_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    ignored_paths = [
        path.replace("/", "\\")
        for path in plan_fixtures._ignored_paths(
            tmp_path,
            reports_root,
            include_readiness_outputs=True,
        )
    ]
    ignored_paths.append("reports\\pipeline_audit\\future.json")

    report = _build(tmp_path, ignored_paths=sorted(ignored_paths))

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["unignored_expected_generated_output_count"] == 0


def test_unignored_planned_outputs_fail_closed(tmp_path: Path, monkeypatch) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        _setup(tmp_path, write_outputs=True)
    )
    full_ignored_paths = _expected_output_paths(
        tmp_path,
        work_order=work_order,
        drilldown=drilldown,
        checkpoint=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=candidate_raw_root,
        output_root=output_root,
        raw_alignment_report=raw_alignment_report,
    )
    original_plan_build_report = runner.plan_gate.build_report

    def ready_plan_build_report(**kwargs):
        kwargs["ignored_generated_paths"] = full_ignored_paths
        return original_plan_build_report(**kwargs)

    monkeypatch.setattr(runner.plan_gate, "build_report", ready_plan_build_report)
    report = runner.build_report(
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
        ignored_generated_paths=[],
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["unignored_expected_generated_output_count"] == 8
    assert any(
        check["name"] == "planned_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_execute_requires_approval_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token="wrong")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "execution_approval_token_present_when_execute"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_execute_runs_fake_commands_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        module = " ".join(argv[:3])
        if "scripts.validation.drilldown_phase2_readiness_blockers" in module:
            path = cwd / _arg_value(argv, "--json-out")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
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
        elif "scripts.validation.audit_raw_dbn_alignment" in module:
            json_out = cwd / _arg_value(argv, "--json-out")
            md_out = cwd / _arg_value(argv, "--md-out")
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "raw_root": _arg_value(argv, "--raw-root"),
                        "market_year_include_list_applied": True,
                        "requested_market_years": [{"market": "ES", "year": 2026}],
                    }
                ),
                encoding="utf-8",
            )
            md_out.write_text("# alignment\n", encoding="utf-8")
        elif "scripts.phase2_causal_base.build_causal_base_data" in module:
            for flag, payload in [
                ("--readiness-json-out", {"status": "PASS", "selected_market_year_count": 1}),
                ("--readiness-md-out", "# readiness\n"),
                ("--readiness-checkpoint-jsonl", '{"stage":"done"}\n'),
            ]:
                path = cwd / _arg_value(argv, flag)
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, dict):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                else:
                    path.write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 3
    assert report["summary"]["generated_output_count"] == 8
    assert report["summary"]["pre_run_artifacts_written"] == 2
    assert report["summary"]["readiness_rerun_approved"] is True
    assert report["summary"]["causal_base_repair_approved"] is False
    assert len(calls) == 3
    include_payloads = [
        json.loads((tmp_path / path).read_text(encoding="utf-8"))
        for path in report["written_pre_run_artifacts"]
    ]
    assert include_payloads == [
        {"market_years": [{"market": "ES", "year": 2026}]},
        {"market_years": [{"market": "ES", "year": 2026}]},
    ]


def test_execute_fails_closed_on_bad_readiness_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_readiness_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        module = " ".join(argv[:3])
        if "scripts.validation.drilldown_phase2_readiness_blockers" in module:
            path = cwd / _arg_value(argv, "--json-out")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"selected_market_year_count": 1}), encoding="utf-8")
        elif "scripts.validation.audit_raw_dbn_alignment" in module:
            json_out = cwd / _arg_value(argv, "--json-out")
            md_out = cwd / _arg_value(argv, "--md-out")
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "raw_root": _arg_value(argv, "--raw-root"),
                        "market_year_include_list_applied": True,
                    }
                ),
                encoding="utf-8",
            )
            md_out.write_text("# alignment\n", encoding="utf-8")
        elif "scripts.phase2_causal_base.build_causal_base_data" in module:
            for flag, payload in [
                ("--readiness-json-out", {"status": "FAIL", "selected_market_year_count": 1}),
                ("--readiness-md-out", "# readiness\n"),
                ("--readiness-checkpoint-jsonl", '{"stage":"done"}\n'),
            ]:
                path = cwd / _arg_value(argv, flag)
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(payload, dict):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                else:
                    path.write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=bad_readiness_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["output_failure_count"] > 0
    assert any(
        check["name"] == "candidate_readiness_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_prerequisites_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = (
        _setup(tmp_path, write_outputs=False)
    )
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
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
    assert f"{runner.STAGE} status={runner.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
