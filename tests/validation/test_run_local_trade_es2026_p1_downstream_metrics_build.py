from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as gate
from scripts.validation import run_local_trade_es2026_p1_downstream_metrics_build as runner
from tests.validation import test_build_local_trade_es2026_p1_downstream_metrics_gate as gate_fixtures


def _paths(tmp_path: Path) -> dict[str, Path]:
    return gate_fixtures._paths(tmp_path)


def _expected_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return gate_fixtures._expected_metrics_artifacts(paths, tmp_path)


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
            "model_output_status": "FAIL",
            "phase8_config_status": "PASS",
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
        feature_output_root=paths["feature_output_root"],
        feature_reports_root=paths["feature_reports_root"],
        wfa_split_reports_root=paths["wfa_split_reports_root"],
        predictions_root=paths["predictions_root"],
        model_reports_root=paths["model_reports_root"],
        metrics_root=paths["metrics_root"],
        model_selection_root=paths["model_selection_root"],
        phase8_root=paths["phase8_root"],
        profile_config=paths["profile_config"],
        models_config=paths["models_config"],
        costs_config=paths["costs_config"],
        phase8_script=paths["phase8_script"],
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


def _write_valid_metrics_outputs(
    cwd: Path,
    argv: Sequence[str],
    *,
    failure_count: int = 0,
    final_holdout_touched: bool = False,
) -> None:
    run = _arg_value(argv, "--run")
    metrics_root = cwd / _arg_value(argv, "--metrics-root")
    model_selection_root = cwd / _arg_value(argv, "--model-selection-root")
    phase8_root = cwd / _arg_value(argv, "--phase8-root")
    predictions = _arg_value(argv, "--predictions")
    predictions_manifest = _arg_value(argv, "--predictions-manifest")
    costs_config = _arg_value(argv, "--costs-config")
    models_config = _arg_value(argv, "--models-config")
    metrics_root.mkdir(parents=True, exist_ok=True)
    model_selection_root.mkdir(parents=True, exist_ok=True)
    phase8_root.mkdir(parents=True, exist_ok=True)
    failures = [] if failure_count == 0 else ["bad metrics output"]
    metrics_payload = {
        "run": run,
        "input_root": str(Path(predictions).parent).replace("\\", "/"),
        "output_root": _arg_value(argv, "--metrics-root"),
        "prediction_path": predictions,
        "predictions_manifest_path": predictions_manifest,
        "costs_config": costs_config,
        "models_config": models_config,
        "prediction_count": 5,
        "policy_row_count": 5,
        "failure_count": failure_count,
        "warning_count": 0,
        "failures": failures,
        "warnings": [],
        "research_policy_metrics_ready": failure_count == 0,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "final_holdout_touched": final_holdout_touched,
        "trading_semantics_changed": False,
        "promotion_gate": {
            "research_alpha_ready": False,
            "model_promotion_allowed": False,
            "promotion_blockers": ["diagnostics only"],
        },
        "live_execution_ready": False,
        "metrics": {"overall": {"row_count": 5, "trade_count": 2}},
    }
    selection_payload = {
        "run": run,
        "input_root": str(Path(predictions).parent).replace("\\", "/"),
        "output_root": _arg_value(argv, "--model-selection-root"),
        "prediction_path": predictions,
        "prediction_manifest_path": predictions_manifest,
        "models_config": models_config,
        "prediction_manifest_artifact_evidence_ready": True,
        "selection_status": "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY",
        "selected_model_id": None,
        "final_holdout_excluded_from_selection": True,
        "failure_count": failure_count,
        "warning_count": 0,
        "failures": failures,
        "warnings": [],
        "promotion_gate": metrics_payload["promotion_gate"],
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "live_execution_ready": False,
    }
    calibration_payload = {
        "run": run,
        "input_root": str(Path(predictions).parent).replace("\\", "/"),
        "output_root": _arg_value(argv, "--model-selection-root"),
        "prediction_path": predictions,
        "predictions_manifest_path": predictions_manifest,
        "failure_count": failure_count,
        "warning_count": 0,
        "failures": failures,
    }
    alpha_payload = {
        "run": run,
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_gate": metrics_payload["promotion_gate"],
        "blockers": ["diagnostics only"],
        "costed_oos": {"row_count": 5},
        "markets": [],
        "folds": [],
        "final_holdout_touched": final_holdout_touched,
        "used_final_holdout_for_tuning": False,
        "trading_semantics_changed": False,
        "failure_count": failure_count,
        "warning_count": 0,
        "failures": failures,
        "warnings": [],
    }
    (metrics_root / f"{run}_metrics.json").write_text(json.dumps(metrics_payload), encoding="utf-8")
    (phase8_root / "metrics.json").write_text(json.dumps(metrics_payload), encoding="utf-8")
    (model_selection_root / "model_selection_report.json").write_text(
        json.dumps(selection_payload),
        encoding="utf-8",
    )
    (model_selection_root / "calibration_report.json").write_text(
        json.dumps(calibration_payload),
        encoding="utf-8",
    )
    (phase8_root / "alpha_promotion_decision.json").write_text(
        json.dumps(alpha_payload),
        encoding="utf-8",
    )
    (metrics_root / f"{run}_metrics.csv").write_text("scope,row_count\noverall,5\n", encoding="utf-8")
    (metrics_root / "turnover_diagnostics.csv").write_text("scope,turnover\noverall,0.1\n", encoding="utf-8")
    (model_selection_root / "model_comparison.csv").write_text(
        "model_id,score\nridge_return_v1,0.0\n",
        encoding="utf-8",
    )


def test_ready_gate_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 1
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["phase8_metrics_approved"] is False
    assert report["summary"]["model_selection_approved"] is False
    assert report["summary"]["model_promotion_approved"] is False


def test_gate_no_go_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_planned"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "downstream_metrics_gate_ready"
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


def test_stale_candidate_metrics_root_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    stale_path = paths["metrics_root"] / "old.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_metrics_roots_empty_before_execution"
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


def test_execute_runs_fake_metrics_command_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        _write_valid_metrics_outputs(cwd, argv)
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["generated_output_count"] == 8
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["phase8_metrics_approved"] is True
    assert report["summary"]["model_selection_approved"] is True
    assert report["summary"]["model_promotion_approved"] is False
    assert len(calls) == 1


def test_existing_completed_outputs_are_reported_when_gate_blocks_overwrite(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    argv = [
        "--run",
        gate.DEFAULT_RUN,
        "--metrics-root",
        gate.rel(paths["metrics_root"], tmp_path),
        "--model-selection-root",
        gate.rel(paths["model_selection_root"], tmp_path),
        "--phase8-root",
        gate.rel(paths["phase8_root"], tmp_path),
        "--predictions",
        gate.rel(paths["predictions_root"] / gate.DEFAULT_RUN / "oos_predictions.parquet", tmp_path),
        "--predictions-manifest",
        gate.rel(
            paths["model_reports_root"] / f"{gate.DEFAULT_RUN}_predictions_manifest.json",
            tmp_path,
        ),
        "--costs-config",
        gate.rel(paths["costs_config"], tmp_path),
        "--models-config",
        gate.rel(paths["models_config"], tmp_path),
    ]
    _write_valid_metrics_outputs(tmp_path, argv)

    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["existing_expected_generated_output_count"] == 8
    assert report["planned_command"]["expected_generated_artifacts"] == _expected_artifacts(
        paths,
        tmp_path,
    )


def test_execute_fails_closed_on_bad_metrics_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        _write_valid_metrics_outputs(cwd, argv, final_holdout_touched=True)
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
        check["name"] == "phase8_metrics_outputs_valid"
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
