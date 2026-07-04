from __future__ import annotations

import json
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_es2026_p1_downstream_wfa_split_gate as gate


def _write_wfa_script(tmp_path: Path, *, missing_feature_manifest: bool = False) -> Path:
    flags = [
        "--profile",
        "--input-root",
        "--reports-root",
        "--profile-config",
        "--models-config",
        "--markets",
        "--years",
    ]
    if not missing_feature_manifest:
        flags.append("--feature-manifest")
    path = tmp_path / "scripts" / "phase5_wfa" / "build_wfa_splits.py"
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


def _write_profile_config(
    path: Path,
    *,
    markets: list[str] | None = None,
    years: list[int] | None = None,
) -> Path:
    markets = markets or ["ES"]
    years = years or [2026]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
defaults:
  final_holdout_years: [2025]
profile_defaults:
  smoke:
    train_days: 2
    test_days: 1
    step_days: 1
  long_research:
    train_days: 2
    test_days: 1
    step_days: 1
profiles:
  tier_3_forward:
    settings_profile: long_research
    markets: {markets}
    years: {years}
    forbid_research_use: true
  local_trade_es2026_p1_research_smoke:
    settings_profile: smoke
    intent: local_trade_es2026_p1_research_smoke
    markets: {markets}
    years: {years}
    feature_manifest_profile: tier_3_forward
    feature_manifest_resolved_profile: tier_3_forward
    forbid_research_use: false
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
purge:
  entry_lag_bars: 1
  target_horizon_bars: 2
  purge_bars: auto
  resolved_purge_bars: 3
model_selection_reports:
  final_holdout_excluded_from_selection: true
""".strip(),
        encoding="utf-8",
    )
    return path


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
        "profile_config": _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml"),
        "models_config": _write_models_config(tmp_path / "configs" / "models.yaml"),
        "wfa_script": _write_wfa_script(tmp_path),
    }


def _expected_wfa_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [gate.rel(path, tmp_path) for path in gate._expected_wfa_artifacts(reports_root=paths["wfa_reports_root"])]


def _write_feature_outputs(paths: dict[str, Path], tmp_path: Path, *, status: str = "WARN") -> None:
    output_root = paths["feature_output_root"]
    reports_root = paths["feature_reports_root"]
    output_path = output_root / "ES" / "2026.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake feature parquet")
    output_hash = file_sha256(output_path)
    output_root.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "feature_cols.json": ["feature_ret_1", "feature_ret_5"],
        "target_cols.json": ["target_valid"],
        "metadata_cols.json": ["ts", "market", "year"],
        "excluded_cols.json": ["open", "close"],
    }.items():
        (output_root / name).write_text(json.dumps(payload), encoding="utf-8")
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / "feature_registry.json").write_text(
        json.dumps(
            {
                "feature_cols": ["feature_ret_1", "feature_ret_5"],
                "feature_audit_gate": {"status": "PASS", "failure_count": 0},
            }
        ),
        encoding="utf-8",
    )
    (reports_root / "feature_audit.json").write_text(
        json.dumps(
            [
                {"feature": "feature_ret_1", "family": "baseline_ohlcv"},
                {"feature": "feature_ret_5", "family": "baseline_ohlcv"},
            ]
        ),
        encoding="utf-8",
    )
    (reports_root / "feature_correlation_report.csv").write_text(
        "feature_a,feature_b,corr\n",
        encoding="utf-8",
    )
    manifest = {
        "status": status,
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "markets": ["ES"],
        "years": [2026],
        "input_root": gate.rel(paths["label_output_root"], tmp_path),
        "output_root": gate.rel(output_root, tmp_path),
        "reports_root": gate.rel(reports_root, tmp_path),
        "failure_count": 0,
        "failures": [],
        "forbidden_feature_leakage_failures": [],
        "feature_count": 2,
        "input_selection": {
            "selected_input_count": 1,
            "requested_markets": ["ES"],
            "requested_years": [2026],
            "selected_markets": ["ES"],
            "selected_years": [2026],
        },
        "label_manifest_gate": {
            "status": "PASS",
            "manifest_path": gate.rel(paths["label_reports_root"] / "label_manifest.json", tmp_path),
            "label_manifest_causal_base_manifest_gate": {"status": "PASS"},
        },
        "output_file_hashes": {
            gate.rel(output_path, tmp_path): output_hash,
        },
        "outputs": [
            {
                "market": "ES",
                "year": 2026,
                "output_path": gate.rel(output_path, tmp_path),
                "status": status,
                "failure_count": 0,
                "failures": [],
            }
        ],
    }
    report = {
        "status": status,
        "input_selection": {
            "selected_markets": ["ES"],
            "selected_years": [2026],
        },
        "files": [{"market": "ES", "year": 2026, "status": status, "failure_count": 0}],
    }
    (reports_root / "baseline_feature_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (reports_root / "baseline_feature_report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    paths = _paths(tmp_path)
    if overrides.get("non_exact_profile"):
        paths["profile_config"] = _write_profile_config(
            tmp_path / "configs" / "alpha_tiered.yaml",
            markets=["CL"],
        )
    if overrides.get("missing_feature_manifest_flag"):
        paths["wfa_script"] = _write_wfa_script(tmp_path, missing_feature_manifest=True)
    if overrides.get("write_feature_outputs", True):
        _write_feature_outputs(paths, tmp_path)
    return gate.build_report(
        repo_root=tmp_path,
        **paths,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
        ignored_generated_paths=overrides.get(
            "ignored_generated_paths",
            _expected_wfa_artifacts(paths, tmp_path),
        ),
    )


def test_ready_gate_defines_exact_phase5_wfa_split_command(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 2
    assert report["summary"]["ignored_expected_generated_output_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["wfa_split_plan_approved"] is False
    approval = report["approval_gate"]
    assert approval["approval_required"] is True
    assert approval["approval_token"] == gate.APPROVAL_TOKEN
    assert approval["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert approval["expected_ignored_artifacts"] == [
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.csv",
        "reports/wfa/local_trade_es2026_p1_candidate/split_plan.json",
    ]
    command = approval["exact_command"]
    assert command.startswith("python -m scripts.phase5_wfa.build_wfa_splits")
    assert f"--profile {gate.TARGET_PROFILE}" in command
    assert "--input-root data/feature_matrices/local_trade_es2026_p1_candidate" in command
    assert "--feature-manifest reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_manifest.json" in command
    assert "--markets ES" in command
    assert "--years 2026" in command
    assert "--allow-final-holdout" not in command
    assert "--data-audit-universe-json" not in command
    assert "model_training_or_selection" in approval["forbidden_actions_without_separate_approval"]


def test_missing_feature_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_feature_outputs=False)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "feature_outputs_exact_es2026_pass"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fully_unavailable_feature_warning_blocks_wfa_approval(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_feature_outputs(paths, tmp_path)
    manifest_path = paths["feature_reports_root"] / "baseline_feature_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["warnings"] = ["features fully unavailable: feature_rel_ret_vs_ZN_15"]
    manifest["outputs"][0]["warnings"] = ["features fully unavailable: feature_rel_ret_vs_ZN_15"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = gate.build_report(
        repo_root=tmp_path,
        **paths,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_wfa_artifacts(paths, tmp_path),
    )

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "feature_fully_unavailable_warnings_resolved"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_exact_es_only_unavailable_feature_warning_is_accepted_for_wfa_splits(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _write_feature_outputs(paths, tmp_path)
    manifest_path = paths["feature_reports_root"] / "baseline_feature_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    warning = gate.wfa_splits.ES_ONLY_FULLY_UNAVAILABLE_INTERMARKET_WARNING
    manifest["warning_count"] = 1
    manifest["warnings"] = []
    manifest["outputs"][0]["warning_count"] = 1
    manifest["outputs"][0]["warnings"] = [warning]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = gate.build_report(
        repo_root=tmp_path,
        **paths,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_wfa_artifacts(paths, tmp_path),
    )

    assert report["summary"]["status"] == gate.STATUS_READY
    assert any(
        check["name"] == "feature_fully_unavailable_warnings_resolved"
        for check in report["checks"]
        if check["status"] == "PASS"
    )


def test_non_exact_wfa_profile_scope_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, non_exact_profile=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "phase5_wfa_profile_scope_exact_es2026"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_feature_manifest_flag_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_feature_manifest_flag=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "phase5_wfa_cli_has_required_controls"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_expected_wfa_output_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _expected_wfa_artifacts(paths, tmp_path)[:-1]

    report = _build(tmp_path, ignored_generated_paths=ignored)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_wfa_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_gate_packet_is_compact(tmp_path: Path) -> None:
    report = _build(tmp_path)
    packet = gate.gate_packet(report)

    assert packet["stage"] == gate.STAGE
    assert packet["status"] == gate.STATUS_READY
    assert packet["approval_gate"]["approval_token"] == gate.APPROVAL_TOKEN
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
