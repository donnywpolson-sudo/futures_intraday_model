from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_es2026_p1_downstream_label_gate as gate
from scripts.validation import run_local_trade_es2026_p1_downstream_label_build as runner


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "candidate_causal_root": tmp_path
        / "data"
        / "causally_gated_normalized"
        / "local_trade_es2026_p1_candidate",
        "label_output_root": tmp_path / "data" / "labeled" / "local_trade_es2026_p1_candidate",
        "label_reports_root": tmp_path / "reports" / "labels" / "local_trade_es2026_p1_candidate",
        "build_reports_root": tmp_path
        / "reports"
        / "pipeline_audit"
        / "local_trade_es2026_p1_causal_base_build_v1",
        "profile_config": tmp_path / "configs" / "alpha_tiered.yaml",
        "costs_config": tmp_path / "configs" / "costs.yaml",
        "label_script": tmp_path / "scripts" / "phase3_labels" / "build_labels.py",
    }


def _expected_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        gate.rel(tmp_path / artifact, tmp_path)
        for artifact in gate._expected_label_artifacts(
            output_root=paths["label_output_root"],
            reports_root=paths["label_reports_root"],
        )
    ]


def _gate_report(tmp_path: Path, *, status: str = gate.STATUS_READY) -> dict[str, object]:
    paths = _paths(tmp_path)
    expected_artifacts = _expected_artifacts(paths, tmp_path)
    command = gate._label_command(
        input_root=Path(gate.rel(paths["candidate_causal_root"], tmp_path)),
        output_root=Path(gate.rel(paths["label_output_root"], tmp_path)),
        reports_root=Path(gate.rel(paths["label_reports_root"], tmp_path)),
        causal_base_manifest=Path(
            gate.rel(paths["build_reports_root"] / "causal_base_manifest.json", tmp_path)
        ),
        profile_config=Path(gate.rel(paths["profile_config"], tmp_path)),
        costs_config=Path(gate.rel(paths["costs_config"], tmp_path)),
        accepted_readiness_exceptions=Path(gate.rel(paths["profile_config"], tmp_path)),
    )
    return {
        "summary": {
            "stage": gate.STAGE,
            "status": status,
            "market": "ES",
            "year": 2026,
            "profile": "tier_3_forward",
            "expected_generated_output_count": len(expected_artifacts),
            "ignored_expected_generated_output_count": len(expected_artifacts),
            "unignored_expected_generated_output_count": 0,
            "existing_expected_generated_output_count": 0,
            "generated_output_count": 0,
            "commands_executed": 0,
            "staged_generated_path_count": 0,
            "failure_count": 0 if status == gate.STATUS_READY else 1,
        },
        "approval_gate": {}
        if status != gate.STATUS_READY
        else {
            "approval_required": True,
            "approval_token": runner.APPROVAL_TOKEN,
            "command_family": "phase3_label_build_exact_es2026_candidate",
            "exact_command": command,
            "timeout_seconds": gate.DEFAULT_TIMEOUT_SECONDS,
            "expected_ignored_artifacts": expected_artifacts,
        },
        "checks": [],
    }


def _build(
    tmp_path: Path,
    *,
    execute: bool = False,
    approval_token: str | None = None,
    command_runner=runner._default_command_runner,
    gate_report: dict[str, object] | None = None,
    ignored_paths: list[str] | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    paths = _paths(tmp_path)
    return runner.build_report(
        repo_root=tmp_path,
        **paths,
        execute=execute,
        approval_token=approval_token,
        command_runner=command_runner,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else _expected_artifacts(paths, tmp_path),
        gate_report=gate_report if gate_report is not None else _gate_report(tmp_path),
    )


def _arg_value(argv: Sequence[str], flag: str) -> str:
    index = list(argv).index(flag)
    return str(argv[index + 1])


def _write_valid_label_outputs(cwd: Path, argv: Sequence[str]) -> None:
    output_root = cwd / _arg_value(argv, "--output-root")
    reports_root = cwd / _arg_value(argv, "--reports-root")
    input_root = _arg_value(argv, "--input-root")
    output_root_arg = _arg_value(argv, "--output-root")
    reports_root_arg = _arg_value(argv, "--reports-root")
    manifest_path_arg = _arg_value(argv, "--causal-base-manifest")
    output_path = output_root / "ES" / "2026.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake parquet bytes")
    output_hash = file_sha256(output_path)
    reports_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "stage": "labels",
        "status": "PASS",
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "markets": ["ES"],
        "years": [2026],
        "input_root": input_root,
        "output_root": output_root_arg,
        "reports_root": reports_root_arg,
        "failure_count": 0,
        "failures": [],
        "input_selection": {
            "selected_input_count": 1,
            "requested_markets": ["ES"],
            "requested_years": [2026],
            "selected_markets": ["ES"],
            "selected_years": [2026],
        },
        "causal_base_manifest_gate": {
            "status": "PASS",
            "manifest_path": manifest_path_arg,
            "expected_market_year_count": 1,
            "accepted_readiness_exception_count": 1,
            "accepted_readiness_exceptions_path": "configs/alpha_tiered.yaml",
        },
        "output_file_hashes": {
            "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet": output_hash,
        },
        "outputs": [
            {
                "market": "ES",
                "year": 2026,
                "output_path": "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
                "status": "PASS",
                "failure_count": 0,
                "failures": [],
            }
        ],
    }
    report = {
        "stage": "labels",
        "status": "PASS",
        "markets": ["ES"],
        "years": [2026],
    }
    (reports_root / "label_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (reports_root / "label_report.json").write_text(json.dumps(report), encoding="utf-8")


def test_ready_gate_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 1
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 3
    assert report["summary"]["ignored_expected_generated_output_count"] == 3
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["label_build_approved"] is False


def test_gate_no_go_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "downstream_label_gate_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_execute_requires_exact_approval_token(tmp_path: Path) -> None:
    report = _build(tmp_path, execute=True, approval_token="wrong")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "execution_approval_token_present_when_execute"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_stale_candidate_label_root_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    stale_path = paths["label_reports_root"] / "old.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "candidate_label_roots_empty_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_expected_output_fails_closed(tmp_path: Path) -> None:
    ignored = _expected_artifacts(_paths(tmp_path), tmp_path)[:-1]

    report = _build(tmp_path, ignored_paths=ignored)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "planned_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_execute_runs_fake_label_command_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        _write_valid_label_outputs(cwd, argv)
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["generated_output_count"] == 3
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["label_build_approved"] is True
    assert report["summary"]["feature_matrix_build_approved"] is False
    assert len(calls) == 1


def test_existing_exact_label_outputs_are_completed_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    command = _gate_report(tmp_path)["approval_gate"]["exact_command"]
    _write_valid_label_outputs(tmp_path, runner._command_to_argv(str(command)))

    report = _build(
        tmp_path,
        gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO),
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["generated_output_count"] == 3
    assert report["summary"]["output_failure_count"] == 0
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["label_build_approved"] is True
    assert any(
        check["name"] == "phase3_label_outputs_valid" and check["status"] == "PASS"
        for check in report["checks"]
    )


def test_execute_fails_closed_on_bad_label_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        _write_valid_label_outputs(cwd, argv)
        reports_root = cwd / _arg_value(argv, "--reports-root")
        manifest = json.loads((reports_root / "label_manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "WARN"
        (reports_root / "label_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=bad_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["output_failure_count"] > 0
    assert any(
        check["name"] == "phase3_label_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_missing_gate_prerequisites_returns_no_go(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(["--repo-root", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{runner.STAGE} status={runner.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
