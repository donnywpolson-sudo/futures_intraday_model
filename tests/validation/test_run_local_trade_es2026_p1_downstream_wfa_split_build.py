from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as gate
from scripts.validation import run_local_trade_es2026_p1_downstream_wfa_split_build as runner


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "label_output_root": tmp_path / "data" / "labeled" / "local_trade_es2026_p1_candidate",
        "label_reports_root": tmp_path / "reports" / "labels" / "local_trade_es2026_p1_candidate",
        "feature_output_root": tmp_path
        / "data"
        / "feature_matrices"
        / "local_trade_es2026_p1_candidate",
        "feature_reports_root": tmp_path
        / "reports"
        / "features_baseline"
        / "local_trade_es2026_p1_candidate",
        "wfa_reports_root": tmp_path / "reports" / "wfa" / "local_trade_es2026_p1_candidate",
        "profile_config": tmp_path / "configs" / "alpha_tiered.yaml",
        "models_config": tmp_path / "configs" / "models.yaml",
        "wfa_script": tmp_path / "scripts" / "phase5_wfa" / "build_wfa_splits.py",
    }


def _expected_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [gate.rel(path, tmp_path) for path in gate._expected_wfa_artifacts(reports_root=paths["wfa_reports_root"])]


def _gate_report(tmp_path: Path, *, status: str = gate.STATUS_READY) -> dict[str, object]:
    paths = _paths(tmp_path)
    expected_artifacts = _expected_artifacts(paths, tmp_path)
    command = gate._wfa_command(
        profile=gate.TARGET_PROFILE,
        input_root=Path(gate.rel(paths["feature_output_root"], tmp_path)),
        reports_root=Path(gate.rel(paths["wfa_reports_root"], tmp_path)),
        profile_config=Path(gate.rel(paths["profile_config"], tmp_path)),
        models_config=Path(gate.rel(paths["models_config"], tmp_path)),
        feature_manifest=Path(
            gate.rel(paths["feature_reports_root"] / "baseline_feature_manifest.json", tmp_path)
        ),
    )
    return {
        "summary": {
            "stage": gate.STAGE,
            "status": status,
            "market": "ES",
            "year": 2026,
            "profile": gate.TARGET_PROFILE,
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
            "command_family": "phase5_wfa_split_plan_exact_es2026_candidate",
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


def _write_valid_wfa_outputs(cwd: Path, argv: Sequence[str], *, failure_count: int = 0) -> None:
    reports_root = cwd / _arg_value(argv, "--reports-root")
    input_root = _arg_value(argv, "--input-root")
    feature_manifest = _arg_value(argv, "--feature-manifest")
    reports_root.mkdir(parents=True, exist_ok=True)
    folds = [
        {
            "fold_id": "ES_research_0001",
            "market": "ES",
            "year": 2026,
            "split_group": "research",
            "is_final_holdout": False,
            "train_rows_before_purge": 12,
            "train_rows_after_purge": 9,
            "purged_train_rows": 3,
            "test_rows": 4,
            "resolved_purge_bars": 3,
            "purge_bars": 3,
            "embargo_bars": 3,
            "selection_allowed": True,
        }
    ]
    manifest = {
        "profile": gate.TARGET_PROFILE,
        "resolved_profile": gate.TARGET_PROFILE,
        "feature_manifest_profile": gate.FEATURE_MANIFEST_PROFILE,
        "feature_manifest_resolved_profile": gate.FEATURE_MANIFEST_PROFILE,
        "input_root": input_root,
        "output_root": _arg_value(argv, "--reports-root"),
        "reports_root": _arg_value(argv, "--reports-root"),
        "markets": ["ES"],
        "years": [2026],
        "purge_policy": {
            "purge_bars": 3,
            "resolved_purge_bars": 3,
            "embargo_bars": 3,
        },
        "final_holdout_policy": {
            "final_holdout_years": [2025],
            "final_holdout_tuning_allowed": False,
            "final_holdout_excluded_from_selection": True,
        },
        "fold_count": len(folds),
        "fold_count_by_market": {"ES": len(folds)},
        "failure_count": failure_count,
        "failures": [] if failure_count == 0 else ["bad split"],
        "feature_manifest_gate": {
            "status": "PASS",
            "manifest_path": feature_manifest,
            "expected_output_root": input_root,
        },
        "folds": folds,
    }
    (reports_root / "split_plan.json").write_text(json.dumps(manifest), encoding="utf-8")
    (reports_root / "split_plan.csv").write_text(
        "fold_id,market,year,split_group,train_rows_after_purge,test_rows,resolved_purge_bars,selection_allowed\n"
        "ES_research_0001,ES,2026,research,9,4,3,True\n",
        encoding="utf-8",
    )


def test_ready_gate_is_dry_run_only_without_execute(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_DRY_RUN_READY
    assert report["summary"]["commands_planned"] == 1
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["ignored_expected_generated_output_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["wfa_split_plan_approved"] is False


def test_gate_no_go_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["commands_executed"] == 0
    assert any(
        check["name"] == "downstream_wfa_split_gate_ready"
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


def test_stale_candidate_wfa_reports_root_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    stale_path = paths["wfa_reports_root"] / "old.json"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}", encoding="utf-8")

    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_wfa_reports_root_empty_before_execution"
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


def test_execute_runs_fake_wfa_split_command_and_validates_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])
    calls: list[list[str]] = []

    def fake_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        _write_valid_wfa_outputs(cwd, argv)
        return subprocess.CompletedProcess(list(argv), 0, "ok", "")

    report = _build(
        tmp_path,
        execute=True,
        approval_token=runner.APPROVAL_TOKEN,
        command_runner=fake_runner,
    )

    assert report["summary"]["status"] == runner.STATUS_EXECUTED
    assert report["summary"]["commands_executed"] == 1
    assert report["summary"]["generated_output_count"] == 2
    assert report["summary"]["unexpected_generated_output_count"] == 0
    assert report["summary"]["wfa_split_plan_approved"] is True
    assert report["summary"]["feature_matrix_build_approved"] is False
    assert len(calls) == 1


def test_existing_completed_outputs_are_reported_when_gate_blocks_overwrite(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    argv = [
        "--reports-root",
        gate.rel(paths["wfa_reports_root"], tmp_path),
        "--input-root",
        gate.rel(paths["feature_output_root"], tmp_path),
        "--feature-manifest",
        gate.rel(paths["feature_reports_root"] / "baseline_feature_manifest.json", tmp_path),
    ]
    _write_valid_wfa_outputs(tmp_path, argv)

    report = _build(tmp_path, gate_report=_gate_report(tmp_path, status=gate.STATUS_NO_GO))

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["existing_expected_generated_output_count"] == 2
    assert report["planned_command"]["expected_generated_artifacts"] == _expected_artifacts(
        paths,
        tmp_path,
    )


def test_execute_fails_closed_on_bad_wfa_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_git_staged_generated_paths", lambda repo_root: [])

    def bad_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        _write_valid_wfa_outputs(cwd, argv, failure_count=1)
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
        check["name"] == "phase5_wfa_split_outputs_valid"
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
