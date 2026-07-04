from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_model_gate as gate


def _write_phase6_script(tmp_path: Path, *, missing_report_only: bool = False) -> Path:
    flags = sorted(gate.REQUIRED_PHASE6_FLAGS)
    if missing_report_only:
        flags.remove("--report-only")
    path = tmp_path / "scripts" / "phase7_wfa" / "run_wfa.py"
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


def _write_profile_config(path: Path, *, forbid_research_use: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    forbid_text = "true" if forbid_research_use else "false"
    path.write_text(
        f"""
defaults:
  final_holdout_years: [2025]
profile_defaults:
  long_research:
    train_days: 2
    test_days: 1
    step_days: 1
  smoke:
    train_days: 2
    test_days: 1
    step_days: 1
profiles:
  tier_3_forward:
    settings_profile: long_research
    markets: ["ES"]
    years: [2026]
    forbid_research_use: true
  local_trade_es2026_p1_research_smoke:
    intent: local_trade_es2026_p1_research_smoke
    settings_profile: smoke
    markets: ["ES"]
    years: [2026]
    forbid_research_use: {forbid_text}
aliases: {{}}
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_models_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
  hyperparameter_tuning_allowed_initially: false
models:
  ridge_return_v1:
    stage: phase_7a_linear_controls
    family: ridge_regression
    task: regression
    target: target_ret_15m
    enabled: true
    requires_optional_dependency: false
""".strip(),
        encoding="utf-8",
    )
    return path


def _paths(tmp_path: Path, *, forbid_research_use: bool = False) -> dict[str, Path]:
    return {
        "feature_output_root": tmp_path
        / "data"
        / "feature_matrices"
        / "local_trade_es2026_p1_candidate",
        "feature_reports_root": tmp_path
        / "reports"
        / "features_baseline"
        / "local_trade_es2026_p1_candidate",
        "wfa_split_reports_root": tmp_path / "reports" / "wfa" / "local_trade_es2026_p1_candidate",
        "predictions_root": tmp_path / "data" / "predictions" / "local_trade_es2026_p1_candidate",
        "model_reports_root": tmp_path / "reports" / "wfa" / "local_trade_es2026_p1_candidate_model",
        "profile_config": _write_profile_config(
            tmp_path / "configs" / "alpha_tiered.yaml",
            forbid_research_use=forbid_research_use,
        ),
        "models_config": _write_models_config(tmp_path / "configs" / "models.yaml"),
        "phase6_script": _write_phase6_script(tmp_path),
    }


def _expected_model_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        gate.rel(path, tmp_path)
        for path in gate._expected_model_artifacts(
            predictions_root=paths["predictions_root"],
            reports_root=paths["model_reports_root"],
            run=gate.DEFAULT_RUN,
        )
    ]


def _write_feature_registry(paths: dict[str, Path]) -> None:
    paths["feature_output_root"].mkdir(parents=True, exist_ok=True)
    (paths["feature_output_root"] / "feature_cols.json").write_text(
        json.dumps(["feature_ret_1", "feature_ret_5"]),
        encoding="utf-8",
    )
    paths["feature_reports_root"].mkdir(parents=True, exist_ok=True)
    (paths["feature_reports_root"] / "baseline_feature_manifest.json").write_text(
        json.dumps({"status": "PASS"}),
        encoding="utf-8",
    )


def _write_split_plan(
    paths: dict[str, Path],
    tmp_path: Path,
    *,
    split_group: str = "research",
    selection_allowed: bool = True,
) -> None:
    split_path = paths["wfa_split_reports_root"] / "split_plan.json"
    split_path.parent.mkdir(parents=True, exist_ok=True)
    final_holdout = split_group == "final_holdout"
    payload = {
        "profile": gate.DEFAULT_PROFILE,
        "resolved_profile": gate.DEFAULT_PROFILE,
        "config_hash": None,
        "script_hash": "fixture",
        "input_file_hashes": {},
        "input_root": gate.rel(paths["feature_output_root"], tmp_path),
        "output_root": gate.rel(paths["wfa_split_reports_root"], tmp_path),
        "reports_root": gate.rel(paths["wfa_split_reports_root"], tmp_path),
        "markets": ["ES"],
        "years": [2026],
        "failure_count": 0,
        "failures": [],
        "fold_count": 1,
        "feature_manifest_gate": {
            "status": "PASS",
            "manifest_path": gate.rel(
                paths["feature_reports_root"] / "baseline_feature_manifest.json",
                tmp_path,
            ),
            "expected_output_root": gate.rel(paths["feature_output_root"], tmp_path),
        },
        "folds": [
            {
                "market": "ES",
                "fold_id": f"ES_{split_group}_0001",
                "split_group": split_group,
                "selection_allowed": selection_allowed,
                "is_final_holdout": final_holdout,
                "train_start": "2026-01-01T00:00:00+00:00",
                "purged_train_end": "2026-01-02T00:00:00+00:00",
                "test_start": "2026-01-03T00:00:00+00:00",
                "test_end": "2026-01-04T00:00:00+00:00",
            }
        ],
    }
    split_path.write_text(json.dumps(payload), encoding="utf-8")


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    paths = _paths(tmp_path, forbid_research_use=overrides.get("forbid_research_use", False))
    if overrides.get("missing_report_only_flag"):
        paths["phase6_script"] = _write_phase6_script(tmp_path, missing_report_only=True)
    if overrides.get("write_feature_registry", True):
        _write_feature_registry(paths)
    if overrides.get("write_split_plan", True):
        _write_split_plan(
            paths,
            tmp_path,
            split_group=overrides.get("split_group", "research"),
            selection_allowed=overrides.get("selection_allowed", True),
        )
    return gate.build_report(
        repo_root=tmp_path,
        profile=gate.DEFAULT_PROFILE,
        matrix=gate.DEFAULT_MATRIX,
        run=gate.DEFAULT_RUN,
        **paths,
        max_folds=gate.DEFAULT_MAX_FOLDS,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
        ignored_generated_paths=overrides.get(
            "ignored_generated_paths",
            _expected_model_artifacts(paths, tmp_path),
        ),
    )


def test_ready_gate_defines_bounded_phase6_model_smoke_command(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["selectable_research_fold_count"] == 1
    assert report["summary"]["max_folds"] == 1
    assert report["summary"]["expected_generated_output_count"] == 3
    assert report["summary"]["ignored_expected_generated_output_count"] == 3
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["wfa_model_training_approved"] is False
    approval = report["approval_gate"]
    assert approval["approval_required"] is True
    assert approval["approval_token"] == gate.APPROVAL_TOKEN
    assert approval["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert approval["maximum_scope"]["max_folds"] == 1
    assert approval["maximum_scope"]["model_training"] is True
    assert approval["maximum_scope"]["metrics_or_model_selection"] is False
    command = approval["exact_command"]
    assert command.startswith("python -m scripts.phase6_wfa.run_wfa")
    assert f"--profile {gate.DEFAULT_PROFILE}" in command
    assert "--markets ES" in command
    assert "--max-folds 1" in command
    assert "--write-predictions" in command
    assert "--report-only" not in command
    assert "--no-predictions" not in command
    assert "metrics_or_model_selection" in approval["forbidden_actions_without_separate_approval"]


def test_locked_forward_profile_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, forbid_research_use=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "phase6_profile_research_eligible_exact_es2026"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_forward_split_without_selectable_research_fold_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, split_group="forward", selection_allowed=False)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["selectable_research_fold_count"] == 0
    assert any(
        check["name"] == "wfa_split_plan_has_selectable_research_folds"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_non_research_selectable_fold_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, split_group="restricted", selection_allowed=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    evidence = report["source_evidence"]["wfa_split_plan"]
    assert evidence["non_research_selectable_folds"] == ["ES_restricted_0001"]
    assert any(
        check["name"] == "wfa_split_plan_exact_es2026_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_phase6_cli_control_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_report_only_flag=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "phase6_cli_has_required_controls"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_split_plan_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_split_plan=False)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert report["source_evidence"]["wfa_split_plan"]["selectable_research_fold_count"] == 0


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
    assert packet["selectable_research_fold_count"] == 1
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
