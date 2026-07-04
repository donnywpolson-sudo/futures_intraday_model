from __future__ import annotations

import json
import shlex
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as gate
from scripts.validation import build_local_trade_es2026_p1_downstream_model_gate as model_gate
from scripts.validation import run_local_trade_es2026_p1_downstream_model_build as model_runner
from tests.validation import test_build_local_trade_es2026_p1_downstream_model_gate as model_gate_fixtures
from tests.validation import test_run_local_trade_es2026_p1_downstream_model_build as model_runner_fixtures


def _write_phase8_script(tmp_path: Path, *, missing_phase8_root: bool = False) -> Path:
    flags = sorted(gate.REQUIRED_PHASE8_FLAGS)
    if missing_phase8_root:
        flags.remove("--phase8-root")
    path = tmp_path / "scripts" / "phase8_model_selection" / "evaluate_predictions.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    args = "\n".join(f'    parser.add_argument("{flag}")' for flag in flags)
    path.write_text(
        "import argparse\n\n"
        "def build_arg_parser():\n"
        "    parser = argparse.ArgumentParser()\n"
        f"{args}\n"
        "    return parser\n",
        encoding="utf-8",
    )
    return path


def _write_costs_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
markets:
  ES:
    point_value: 50.0
    tick_value: 12.5
    round_turn_cost_dollars: 10.0
""".strip(),
        encoding="utf-8",
    )
    return path


def _paths(tmp_path: Path) -> dict[str, Path]:
    model_paths = model_gate_fixtures._paths(tmp_path)
    return {
        **model_paths,
        "metrics_root": tmp_path / "reports" / "metrics" / "local_trade_es2026_p1_candidate_model",
        "model_selection_root": tmp_path
        / "reports"
        / "model_selection"
        / "local_trade_es2026_p1_candidate_model",
        "phase8_root": tmp_path / "reports" / "phase8" / "local_trade_es2026_p1_candidate_model",
        "costs_config": _write_costs_config(tmp_path / "configs" / "costs.yaml"),
        "phase8_script": _write_phase8_script(tmp_path),
    }


def _expected_metrics_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        gate.rel(path, tmp_path)
        for path in gate._expected_metrics_artifacts(
            metrics_root=paths["metrics_root"],
            model_selection_root=paths["model_selection_root"],
            phase8_root=paths["phase8_root"],
            run=gate.DEFAULT_RUN,
        )
    ]


def _write_model_outputs(paths: dict[str, Path], tmp_path: Path, *, failure_count: int = 0) -> None:
    model_gate_fixtures._write_feature_registry(paths)
    model_gate_fixtures._write_split_plan(paths, tmp_path)
    model_report = model_gate.build_report(
        repo_root=tmp_path,
        profile=model_gate.DEFAULT_PROFILE,
        matrix=model_gate.DEFAULT_MATRIX,
        run=model_gate.DEFAULT_RUN,
        feature_output_root=paths["feature_output_root"],
        feature_reports_root=paths["feature_reports_root"],
        wfa_split_reports_root=paths["wfa_split_reports_root"],
        predictions_root=paths["predictions_root"],
        model_reports_root=paths["model_reports_root"],
        profile_config=paths["profile_config"],
        models_config=paths["models_config"],
        phase6_script=paths["phase6_script"],
        max_folds=model_gate.DEFAULT_MAX_FOLDS,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=model_gate_fixtures._expected_model_artifacts(paths, tmp_path),
    )
    command = str(model_report["approval_gate"]["exact_command"])
    model_runner_fixtures._write_valid_model_outputs(
        tmp_path,
        model_runner._command_to_argv(command),
        failure_count=failure_count,
    )


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    paths = _paths(tmp_path)
    if overrides.get("missing_phase8_root_flag"):
        paths["phase8_script"] = _write_phase8_script(tmp_path, missing_phase8_root=True)
    if overrides.get("missing_costs_config"):
        paths["costs_config"].unlink()
    if overrides.get("write_model_outputs", True):
        _write_model_outputs(
            paths,
            tmp_path,
            failure_count=overrides.get("model_failure_count", 0),
        )
    return gate.build_report(
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
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
        ignored_generated_paths=overrides.get(
            "ignored_generated_paths",
            _expected_metrics_artifacts(paths, tmp_path),
        ),
    )


def test_ready_gate_defines_exact_phase8_metrics_command(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["model_output_status"] == "PASS"
    assert report["summary"]["phase8_config_status"] == "PASS"
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["phase8_metrics_approved"] is False
    approval = report["approval_gate"]
    assert approval["approval_required"] is True
    assert approval["approval_token"] == gate.APPROVAL_TOKEN
    assert approval["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert approval["maximum_scope"]["reports_mutation"] is True
    assert approval["maximum_scope"]["model_training"] is False
    assert approval["maximum_scope"]["promotion_or_freeze"] is False
    command = approval["exact_command"]
    argv = shlex.split(command)
    assert argv[:3] == ["python", "-m", "scripts.phase8_model_selection.evaluate_predictions"]
    assert "--predictions" in argv
    assert "--predictions-manifest" in argv
    assert "--metrics-root" in argv
    assert "--require-promotion-ready" not in argv
    assert "--allow-negative-net-market" not in argv
    assert "--allow-negative-net-fold" not in argv
    assert "model_promotion_or_artifact_freeze" in approval["forbidden_actions_without_separate_approval"]


def test_missing_model_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_model_outputs=False)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert report["summary"]["model_output_status"] == "FAIL"
    assert any(
        check["name"] == "phase6_model_outputs_exact_es2026_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_bad_model_manifest_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, model_failure_count=1)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["source_evidence"]["model_outputs"]["failure_count"] > 0
    assert any(
        check["name"] == "phase6_model_outputs_exact_es2026_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_phase8_cli_control_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_phase8_root_flag=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "phase8_cli_has_required_controls"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_costs_config_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_costs_config=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["phase8_config_status"] == "FAIL"
    assert any(
        check["name"] == "phase8_configs_present"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_expected_metrics_output_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _expected_metrics_artifacts(paths, tmp_path)[:-1]

    report = _build(tmp_path, ignored_generated_paths=ignored)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_metrics_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_artifact_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged_generated_paths=["reports/generated.json"])

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_gate_packet_is_compact(tmp_path: Path) -> None:
    report = _build(tmp_path)
    packet = gate.gate_packet(report)

    assert packet["stage"] == gate.STAGE
    assert packet["status"] == gate.STATUS_READY
    assert packet["approval_gate"]["approval_token"] == gate.APPROVAL_TOKEN
    assert packet["model_output_status"] == "PASS"
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
