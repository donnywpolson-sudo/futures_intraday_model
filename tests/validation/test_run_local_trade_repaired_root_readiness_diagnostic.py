from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Sequence

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import run_local_trade_repaired_root_readiness_diagnostic as runner
from tests.validation import test_build_local_trade_upstream_manifest_evidence_resolver as fixtures


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_raw_alignment_placeholder(tmp_path: Path) -> Path:
    path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_json(path, {"status": "PASS"})
    return path


def _write_raw_alignment_override(tmp_path: Path, profile: str, year: int) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "raw_alignment" / f"{profile}_{year}.json"
    _write_json(path, {"status": "PASS", "profile": profile, "year": year})
    return path


def _write_projected_candidate_manifest(tmp_path: Path, *, profile: str, year: int) -> None:
    output_path = tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT / "NG" / f"{year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(f"NG {year}".encode("utf-8"))
    manifest = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": profile,
        "resolved_profile": profile,
        "output_root": (tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT).as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "warnings": [],
        "failures": [],
        "summary": {"warn_count": 0, "fail_count": 0},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "NG",
                "year": year,
                "status": "PASS",
                "warning_count": 0,
                "failure_count": 0,
                "warnings": [],
                "failures": [],
            }
        ],
    }
    _write_json(
        tmp_path / "reports" / "pipeline_audit" / "projected_candidate" / f"{profile}_{year}" / "causal_base_manifest.json",
        manifest,
    )


def _write_candidate_projection_evidence(tmp_path: Path) -> None:
    _write_projected_candidate_manifest(tmp_path, profile="tier_3_holdout", year=2025)
    _write_projected_candidate_manifest(tmp_path, profile="tier_3_forward", year=2026)


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    _write_candidate_projection_evidence(tmp_path)
    proposal = fixtures._write_proposal(tmp_path)
    raw_alignment = _write_raw_alignment_placeholder(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "diagnostic_v1"
    return proposal, raw_alignment, reports_root


def _build(
    tmp_path: Path,
    *,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner=None,
) -> dict[str, object]:
    proposal, raw_alignment, reports_root = _setup(tmp_path)
    return runner.build_report(
        repo_root=tmp_path,
        proposal_path=proposal,
        diagnostic_reports_root=reports_root,
        execute=execute,
        approval_token=approval_token,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
        command_runner=command_runner,
    )


def _arg_value(argv: Sequence[str], flag: str) -> str:
    index = list(argv).index(flag)
    return str(argv[index + 1])


def _patch_post_execution_staged_paths(monkeypatch, paths: list[str] | None = None) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: paths or [])


def test_dry_run_is_console_only_and_plans_bounded_argv(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["execute_requested"] is False
    assert report["summary"]["commands_planned"] == 2
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_diagnostic_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    for command in report["planned_commands"]:
        argv = command["argv"]
        assert "--readiness-only" in argv
        assert "--allow-broad-build-after-readiness-pass" not in argv
        assert "--build-max-market-years" not in argv
        assert "--accepted-readiness-exceptions" not in argv


def test_dry_run_uses_per_group_raw_alignment_report_overrides(tmp_path: Path) -> None:
    proposal, raw_alignment, reports_root = _setup(tmp_path)
    holdout_alignment = _write_raw_alignment_override(tmp_path, "tier_3_holdout", 2025)
    forward_alignment = _write_raw_alignment_override(tmp_path, "tier_3_forward", 2026)

    report = runner.build_report(
        repo_root=tmp_path,
        proposal_path=proposal,
        diagnostic_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
        raw_alignment_report_overrides={
            "tier_3_holdout:2025": holdout_alignment.as_posix(),
            "tier_3_forward:2026": forward_alignment.as_posix(),
        },
    )

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    commands = {command["year"]: command for command in report["planned_commands"]}
    assert commands[2025]["raw_alignment_report"] == holdout_alignment.as_posix()
    assert commands[2026]["raw_alignment_report"] == forward_alignment.as_posix()
    assert _arg_value(commands[2025]["argv"], "--raw-alignment-report") == holdout_alignment.as_posix()
    assert _arg_value(commands[2026]["argv"], "--raw-alignment-report") == forward_alignment.as_posix()


def test_execute_requires_exact_approval_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token="wrong")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "execution_approval_token_present_when_execute"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_diagnostic_report_file_blocks_dry_run(tmp_path: Path) -> None:
    proposal, raw_alignment, reports_root = _setup(tmp_path)
    stale_path = reports_root / "stale.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = runner.build_report(
        repo_root=tmp_path,
        proposal_path=proposal,
        diagnostic_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["unexpected_generated_output_count"] == 1
    assert any(
        check["name"] == "diagnostic_reports_root_empty_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_outside_diagnostic_reports_root_does_not_scan_stale_files(tmp_path: Path) -> None:
    proposal, raw_alignment, _reports_root = _setup(tmp_path)
    outside_root = tmp_path / "outside_reports"
    outside_root.mkdir(parents=True, exist_ok=True)
    (outside_root / "stale.json").write_text("{}", encoding="utf-8")

    report = runner.build_report(
        repo_root=tmp_path,
        proposal_path=proposal,
        diagnostic_reports_root=outside_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert any(
        check["name"] == "diagnostic_reports_root_under_reports"
        for check in report["diagnostic_plan_checks"]
        if check["status"] == "FAIL"
    )


def test_execute_writes_include_lists_and_runs_fake_readiness_commands(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        selected_count = int(_arg_value(argv, "--readiness-max-market-years"))
        for flag, payload in [
            ("--readiness-json-out", {"status": "PASS", "selected_market_year_count": selected_count}),
            ("--readiness-md-out", "# readiness\n"),
            ("--readiness-checkpoint-jsonl", '{"stage":"done"}\n'),
        ]:
            path = cwd / _arg_value(argv, flag)
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(payload, dict):
                path.write_text(json.dumps(payload), encoding="utf-8")
            else:
                path.write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "phase2_readiness_only status=PASS", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["readiness_diagnostic_approved"] is True
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["commands_executed"] == 2
    assert report["summary"]["include_list_files_written"] == 2
    assert report["summary"]["generated_output_count"] == 8
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["post_execution_staged_generated_path_count"] == 0
    assert len(calls) == 2
    assert all("--readiness-only" in argv for argv in calls)
    include_payloads = [
        json.loads((tmp_path / path).read_text(encoding="utf-8"))
        for path in report["written_include_lists"]
    ]
    assert {row["year"] for payload in include_payloads for row in payload["market_years"]} == {2025, 2026}


def test_unexpected_extra_report_file_after_success_is_no_go(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)
    calls: list[list[str]] = []

    def noisy_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        selected_count = int(_arg_value(argv, "--readiness-max-market-years"))
        for flag, payload in [
            ("--readiness-json-out", {"status": "PASS", "selected_market_year_count": selected_count}),
            ("--readiness-md-out", "# readiness\n"),
            ("--readiness-checkpoint-jsonl", '{"stage":"done"}\n'),
        ]:
            path = cwd / _arg_value(argv, flag)
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(payload, dict):
                path.write_text(json.dumps(payload), encoding="utf-8")
            else:
                path.write_text(payload, encoding="utf-8")
        reports_root = cwd / _arg_value(argv, "--reports-root")
        (reports_root / "unexpected.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "phase2_readiness_only status=PASS", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=noisy_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 2
    assert report["summary"]["unexpected_generated_output_count"] == 2
    assert calls
    assert any(
        check["name"] == "unexpected_diagnostic_reports_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_post_execution_staged_generated_path_is_no_go(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(
        monkeypatch,
        ["reports/pipeline_audit/local_trade_repaired_root_readiness_diagnostic_v1/include_6E_CL_ES_ZN_2025.json"],
    )
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        selected_count = int(_arg_value(argv, "--readiness-max-market-years"))
        for flag, payload in [
            ("--readiness-json-out", {"status": "PASS", "selected_market_year_count": selected_count}),
            ("--readiness-md-out", "# readiness\n"),
            ("--readiness-checkpoint-jsonl", '{"stage":"done"}\n'),
        ]:
            path = cwd / _arg_value(argv, flag)
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(payload, dict):
                path.write_text(json.dumps(payload), encoding="utf-8")
            else:
                path.write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "phase2_readiness_only status=PASS", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 2
    assert report["summary"]["staged_generated_path_count"] == 1
    assert report["summary"]["post_execution_staged_generated_path_count"] == 1
    assert calls
    assert any(
        check["name"] == "post_execution_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_nonzero_readiness_command_stops_after_first_failure(tmp_path: Path, monkeypatch) -> None:
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
    assert any(check["name"] == "readiness_commands_completed" for check in report["checks"] if check["status"] == "FAIL")


def test_successful_return_without_readable_artifacts_is_no_go(tmp_path: Path, monkeypatch) -> None:
    _patch_post_execution_staged_paths(monkeypatch)
    calls = 0

    def incomplete_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(list(argv), 0, "phase2_readiness_only status=PASS", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=incomplete_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["artifact_failure_count"] == 1
    assert calls == 1
    assert any(
        check["name"] == "readiness_artifacts_present_and_readable"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_dry_run_writes_no_reports(tmp_path: Path, capsys) -> None:
    proposal, raw_alignment, reports_root = _setup(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--diagnostic-reports-root",
            str(reports_root),
            "--raw-alignment-report",
            str(raw_alignment),
            "--expected-eligible-market-count",
            "2",
            "--expected-proof-status-market-year-count",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{runner.STAGE} status={runner.STATUS_DRY_RUN_READY}" in output
    assert "commands_planned=2" in output
    assert "commands_executed=0" in output
    assert "command_failures=0" in output
    assert "artifact_failures=0" in output
    assert "unexpected_generated_outputs=0" in output
    assert "post_execution_staged_generated_paths=0" in output
    assert not reports_root.exists()
