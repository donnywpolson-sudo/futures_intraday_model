from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_es2026_p1_downstream_model_gate as gate
from scripts.validation import run_local_trade_es2026_p1_downstream_model_build as runner
from tests.validation import test_build_local_trade_es2026_p1_downstream_model_gate as gate_fixtures


def _paths(tmp_path: Path) -> dict[str, Path]:
    return gate_fixtures._paths(tmp_path)


def _expected_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return gate_fixtures._expected_model_artifacts(paths, tmp_path)


def _gate_report(tmp_path: Path, *, status: str = gate.STATUS_READY) -> dict[str, object]:
    if status == gate.STATUS_READY:
        return gate_fixtures._build(tmp_path)
    return {
        "summary": {
            "stage": gate.STAGE,
            "status": status,
            "market": "ES",
            "year": 2026,
            "profile": gate.DEFAULT_PROFILE,
            "expected_generated_output_count": 0,
            "ignored_expected_generated_output_count": 0,
            "unignored_expected_generated_output_count": 0,
            "existing_expected_generated_output_count": 0,
            "generated_output_count": 0,
            "commands_executed": 0,
            "staged_generated_path_count": 0,
            "failure_count": 1,
        },
        "approval_gate": {},
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
        profile=gate.DEFAULT_PROFILE,
        matrix=gate.DEFAULT_MATRIX,
        run=gate.DEFAULT_RUN,
        **paths,
        max_folds=gate.DEFAULT_MAX_FOLDS,
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


def _write_valid_model_outputs(
    cwd: Path,
    argv: Sequence[str],
    *,
    failure_count: int = 0,
) -> None:
    run = _arg_value(argv, "--run")
    predictions_root = cwd / _arg_value(argv, "--predictions-root")
    reports_root = cwd / _arg_value(argv, "--reports-root")
    prediction_path = predictions_root / run / "oos_predictions.parquet"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_bytes(b"fake predictions parquet")
    prediction_hash = file_sha256(prediction_path)
    reports_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": gate.DEFAULT_PROFILE,
        "resolved_profile": gate.DEFAULT_PROFILE,
        "matrix": gate.DEFAULT_MATRIX,
        "run": run,
        "markets": ["ES"],
        "years": [2026],
        "model_ids": ["ridge_return_v1"],
        "target_names": ["target_ret_15m"],
        "feature_count": 2,
        "fold_count": 1,
        "unfiltered_selectable_fold_count": 1,
        "fold_selection": {
            "markets": ["ES"],
            "fold_shard_count": None,
            "fold_shard_index": None,
            "max_folds": gate.DEFAULT_MAX_FOLDS,
        },
        "prediction_count": 5,
        "prediction_markets": ["ES"],
        "prediction_years": [2026],
        "duplicate_prediction_count": 0,
        "prediction_writes_enabled": True,
        "prediction_artifact_written": True,
        "prediction_artifact_write_skipped": False,
        "warning_count": 0,
        "failure_count": failure_count,
        "failures": [] if failure_count == 0 else ["bad model output"],
        "artifact_evidence_ready": failure_count == 0,
        "artifact_evidence_failures": [] if failure_count == 0 else ["manifest failure_count is nonzero"],
        "split_plan_path": _arg_value(argv, "--split-plan"),
        "input_root": _arg_value(argv, "--input-root"),
        "predictions_root": _arg_value(argv, "--predictions-root"),
        "reports_root": _arg_value(argv, "--reports-root"),
        "prediction_path": f"{_arg_value(argv, '--predictions-root')}/{run}/oos_predictions.parquet",
        "profile_config_path": _arg_value(argv, "--profile-config"),
        "required_columns": gate.phase6_wfa.PREDICTION_COLUMNS,
        "stale_output_path_exists": False,
        "output_file_hashes": {
            f"{_arg_value(argv, '--predictions-root')}/{run}/oos_predictions.parquet": prediction_hash,
        },
    }
    report = {
        "profile": gate.DEFAULT_PROFILE,
        "resolved_profile": gate.DEFAULT_PROFILE,
        "run": run,
        "prediction_count": 5,
        "prediction_markets": ["ES"],
        "prediction_years": [2026],
        "failure_count": failure_count,
        "failures": [] if failure_count == 0 else ["bad model output"],
        "artifact_evidence_ready": failure_count == 0,
        "artifact_evidence_failures": [] if failure_count == 0 else ["manifest failure_count is nonzero"],
    }
    (reports_root / f"{run}_predictions_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (reports_root / f"{run}_wfa_report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )


def test_ready_gate_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 1
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 3
    assert report["summary"]["ignored_expected_generated_output_count"] == 3
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["wfa_model_training_approved"] is False
    assert report["summary"]["wfa_prediction_write_approved"] is False


def test_gate_no_go_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "downstream_model_gate_ready"
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


def test_stale_candidate_model_root_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    stale_path = paths["model_reports_root"] / "old.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_model_roots_empty_before_execution"
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


def test_execute_runs_fake_model_command_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        _write_valid_model_outputs(cwd, argv)
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
    assert report["summary"]["wfa_model_training_approved"] is True
    assert report["summary"]["wfa_prediction_write_approved"] is True
    assert report["summary"]["wfa_split_plan_approved"] is False
    assert len(calls) == 1


def test_existing_completed_outputs_are_reported_when_gate_blocks_overwrite(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    argv = [
        "--run",
        gate.DEFAULT_RUN,
        "--predictions-root",
        gate.rel(paths["predictions_root"], tmp_path),
        "--reports-root",
        gate.rel(paths["model_reports_root"], tmp_path),
        "--split-plan",
        gate.rel(paths["wfa_split_reports_root"] / "split_plan.json", tmp_path),
        "--input-root",
        gate.rel(paths["feature_output_root"], tmp_path),
        "--profile-config",
        gate.rel(paths["profile_config"], tmp_path),
    ]
    _write_valid_model_outputs(tmp_path, argv)

    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["expected_generated_output_count"] == 3
    assert report["summary"]["existing_expected_generated_output_count"] == 3
    assert report["planned_command"]["expected_generated_artifacts"] == _expected_artifacts(
        paths,
        tmp_path,
    )


def test_execute_fails_closed_on_bad_prediction_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        _write_valid_model_outputs(cwd, argv, failure_count=1)
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
        check["name"] == "phase6_model_outputs_valid"
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
