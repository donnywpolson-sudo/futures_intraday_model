from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.validation import run_local_trade_es2026_p1_candidate_conversion as runner
from tests.validation import test_build_local_trade_es2026_p1_candidate_conversion_plan as plan_fixtures
from tests.validation import test_build_local_trade_es2026_p1_repair_plan as repair_fixtures


def _arg_value(argv: Sequence[str], flag: str) -> str:
    index = list(argv).index(flag)
    return str(argv[index + 1])


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


def _build(
    tmp_path: Path,
    *,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner=runner._default_command_runner,
    write_plans: bool = True,
    write_archives: bool = True,
    staged: list[str] | None = None,
    include_candidate_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path,
        write_plans=write_plans,
        write_archives=write_archives,
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
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else plan_fixtures._ignored_paths(
            tmp_path,
            repair_reports_root,
            include_candidate_outputs=include_candidate_outputs_in_ignored,
        ),
    )


def test_missing_prerequisite_plans_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_plans=False, write_archives=False)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert any(
        check["name"] == "candidate_conversion_plan_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_ready_plan_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 2
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False


def test_filters_windows_style_ignored_planned_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    ignored_paths = [
        path.replace("/", "\\")
        for path in plan_fixtures._ignored_paths(tmp_path, reports_root, include_candidate_outputs=True)
    ]
    ignored_paths.append("reports\\pipeline_audit\\future.json")

    report = _build(
        tmp_path,
        write_plans=True,
        write_archives=True,
        ignored_paths=sorted(ignored_paths),
    )

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0


def test_execute_requires_approval_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "approval_token_required_for_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_planned_outputs_fail_closed(tmp_path: Path, monkeypatch) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path,
        write_plans=True,
        write_archives=True,
    )
    full_ignored_paths = plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_candidate_outputs=True,
    )
    runner_ignored_paths = plan_fixtures._ignored_paths(
        tmp_path,
        repair_reports_root,
        include_candidate_outputs=False,
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
        ignored_generated_paths=runner_ignored_paths,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["unignored_expected_generated_output_count"] == 6
    assert any(
        check["name"] == "planned_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_execute_runs_fake_commands_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        module = " ".join(argv[:3])
        if "scripts.phase1A_download.download_databento_raw" in module:
            raw_root = cwd / _arg_value(argv, "--raw-root")
            reports_root = cwd / _arg_value(argv, "--reports-root")
            parquet_path = raw_root / "ES" / "2026.parquet"
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_path.write_bytes(b"candidate parquet")
            reports_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "databento_convert_results.json",
                "raw_ingest_manifest.json",
                "raw_parquet_manifest.json",
            ):
                (reports_root / name).write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        elif "scripts.validation.audit_enriched_raw_optional_schemas" in module:
            raw_root = cwd / _arg_value(argv, "--raw-root")
            json_out = cwd / _arg_value(argv, "--json-out")
            md_out = cwd / _arg_value(argv, "--md-out")
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(
                json.dumps(
                    {
                        "stage": "raw_enriched_optional_schema_audit",
                        "status": "PASS",
                        "raw_root": raw_root.as_posix(),
                        "file_count": 1,
                        "verdicts": {
                            "optional_status_readiness": "PASS",
                            "optional_statistics_readiness": "PASS",
                        },
                    }
                ),
                encoding="utf-8",
            )
            md_out.write_text("# PASS\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 2
    assert report["summary"]["generated_output_count"] == 6
    assert report["summary"]["candidate_raw_write_approved"] is True
    assert report["summary"]["data_mutation_performed"] is True
    assert len(calls) == 2


def test_execute_fails_closed_on_bad_audit_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_audit_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        module = " ".join(argv[:3])
        if "scripts.phase1A_download.download_databento_raw" in module:
            raw_root = cwd / _arg_value(argv, "--raw-root")
            reports_root = cwd / _arg_value(argv, "--reports-root")
            parquet_path = raw_root / "ES" / "2026.parquet"
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_path.write_bytes(b"candidate parquet")
            reports_root.mkdir(parents=True, exist_ok=True)
            for name in (
                "databento_convert_results.json",
                "raw_ingest_manifest.json",
                "raw_parquet_manifest.json",
            ):
                (reports_root / name).write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        elif "scripts.validation.audit_enriched_raw_optional_schemas" in module:
            json_out = cwd / _arg_value(argv, "--json-out")
            md_out = cwd / _arg_value(argv, "--md-out")
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "raw_root": (cwd / _arg_value(argv, "--raw-root")).as_posix(),
                        "verdicts": {
                            "optional_status_readiness": "FAIL",
                            "optional_statistics_readiness": "PASS",
                        },
                    }
                ),
                encoding="utf-8",
            )
            md_out.write_text("# FAIL\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=bad_audit_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["output_failure_count"] > 0
    assert any(
        check["name"] == "expected_generated_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_prerequisites_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint, repair_reports_root, candidate_raw_root, output_root, raw_alignment_report = _setup(
        tmp_path,
        write_plans=False,
        write_archives=False,
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
    assert not candidate_raw_root.exists()
