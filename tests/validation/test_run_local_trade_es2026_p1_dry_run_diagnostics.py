from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence

from scripts.validation import run_local_trade_es2026_p1_dry_run_diagnostics as runner
from tests.validation import test_build_local_trade_es2026_p1_repair_plan as fixtures


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    work_order, drilldown, checkpoint = fixtures._write_reports(tmp_path)
    repair_reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    return work_order, drilldown, checkpoint, repair_reports_root


def _arg_value(argv: Sequence[str], flag: str) -> str:
    index = list(argv).index(flag)
    return str(argv[index + 1])


def _dry_run_out(plan_out: Path) -> Path:
    return plan_out.with_name(f"{plan_out.stem}_dry_run{plan_out.suffix}")


def _expected_dry_run_paths(repair_reports_root: Path, tmp_path: Path) -> list[str]:
    return sorted(
        [
            (repair_reports_root / "phase1a_statistics" / "databento_download_plan_dry_run.json")
            .relative_to(tmp_path)
            .as_posix(),
            (repair_reports_root / "phase1a_status" / "databento_download_plan_dry_run.json")
            .relative_to(tmp_path)
            .as_posix(),
        ]
    )


def _build(
    tmp_path: Path,
    *,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner=None,
    staged: list[str] | None = None,
    ignored: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root = _setup(tmp_path)
    ignored_paths = _expected_dry_run_paths(repair_reports_root, tmp_path) if ignored is None else ignored
    return runner.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        execute=execute,
        approval_token=approval_token,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths,
        command_runner=command_runner,
    )


def _patch_post_execution_staged_paths(monkeypatch, paths: list[str] | None = None) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: paths or [])


def test_dry_run_is_console_only_and_plans_two_bounded_commands(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 2
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["provider_download_approved"] is False
    assert report["summary"]["data_mutation_performed"] is False

    commands = {command["schema"]: command for command in report["planned_commands"]}
    assert sorted(commands) == ["statistics", "status"]
    for schema, command in commands.items():
        argv = command["argv"]
        assert "--dry-run" in argv
        assert _arg_value(argv, "--symbols") == "ES"
        assert _arg_value(argv, "--schema") == schema
        assert _arg_value(argv, "--start") == "2026-01-01"
        assert _arg_value(argv, "--end") == "2026-06-13"
        assert command["expected_generated_artifacts"][0].endswith("_dry_run.json")


def test_execute_requires_exact_approval_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token="wrong")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "execution_approval_token_present_when_execute"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_report_file_blocks_dry_run(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = _setup(tmp_path)
    stale_path = repair_reports_root / "stale.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = runner.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_dry_run_paths(repair_reports_root, tmp_path),
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "repair_reports_root_empty_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_planned_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, ignored=[])

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["ignored_expected_generated_output_count"] == 0
    assert report["summary"]["unignored_expected_generated_output_count"] == 2
    assert any(
        check["name"] == "planned_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_ignored_planned_outputs_filter_extra_paths(tmp_path: Path) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = _setup(tmp_path)
    ignored_paths = [
        *[path.replace("/", "\\") for path in _expected_dry_run_paths(repair_reports_root, tmp_path)],
        "reports/pipeline_audit/repair_plan_v1/future_step/extra.json",
    ]

    report = runner.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=ignored_paths,
    )

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["ignored_expected_generated_output_count"] == 2
    assert report["summary"]["unignored_expected_generated_output_count"] == 0


def test_execute_runs_fake_dry_run_commands_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        schema = _arg_value(argv, "--schema")
        plan_out = cwd / _arg_value(argv, "--plan-out")
        output_path = _dry_run_out(plan_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "run_kind": "dry_run",
                    "mode": "download-dbn",
                    "schema": schema,
                    "schemas": [schema],
                    "start": "2026-01-01",
                    "end": "2026-06-13",
                    "universe": "custom",
                    "products": ["ES"],
                    "product_count": 1,
                    "task_count": 1,
                    "tasks": [
                        {
                            "product": "ES",
                            "year": 2026,
                            "schema": schema,
                            "start": "2026-01-01",
                            "end": "2026-06-13",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(list(argv), 0, "PLAN", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 2
    assert report["summary"]["generated_output_count"] == 2
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["dry_run_diagnostics_approved"] is True
    assert report["summary"]["provider_download_approved"] is False
    assert len(calls) == 2


def test_wrong_scope_output_is_no_go(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)

    def wrong_scope_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        schema = _arg_value(argv, "--schema")
        output_path = _dry_run_out(cwd / _arg_value(argv, "--plan-out"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "run_kind": "dry_run",
                    "mode": "download-dbn",
                    "schema": schema,
                    "schemas": [schema],
                    "start": "2026-01-01",
                    "end": "2026-06-13",
                    "universe": "custom",
                    "products": ["NQ"],
                    "product_count": 1,
                    "task_count": 1,
                    "tasks": [
                        {
                            "product": "NQ",
                            "year": 2026,
                            "schema": schema,
                            "start": "2026-01-01",
                            "end": "2026-06-13",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(list(argv), 0, "PLAN", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=wrong_scope_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["output_failure_count"] == 2
    assert any(
        check["name"] == "dry_run_plan_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_nonzero_command_stops_after_first_failure(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)
    calls = 0

    def failing_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(list(argv), 2, "", "failed")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=failing_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["command_failure_count"] == 1
    assert calls == 1


def test_cli_dry_run_writes_no_reports(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root = _setup(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\n", encoding="utf-8")
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
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(repair_reports_root / "alignment.json"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{runner.STAGE} status={runner.STATUS_DRY_RUN_READY}" in output
    assert "commands_planned=2" in output
    assert "commands_executed=0" in output
    assert "expected_generated_outputs=2" in output
    assert not repair_reports_root.exists()
