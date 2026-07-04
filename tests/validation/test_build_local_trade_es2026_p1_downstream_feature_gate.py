from __future__ import annotations

from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_feature_gate as gate
from scripts.validation import run_local_trade_es2026_p1_downstream_label_build as label_runner


LABEL_EXPECTED_ARTIFACTS = [
    "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
    "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
    "reports/labels/local_trade_es2026_p1_candidate/label_report.json",
]


def _write_feature_script(tmp_path: Path, *, missing_years: bool = False) -> Path:
    flags = [
        "--profile",
        "--input-root",
        "--output-root",
        "--reports-root",
        "--costs-config",
        "--profile-config",
        "--label-manifest",
        "--markets",
    ]
    if not missing_years:
        flags.append("--years")
    path = tmp_path / "scripts" / "phase4_features" / "build_baseline_features.py"
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
        "profile_config": tmp_path / "configs" / "alpha_tiered.yaml",
        "costs_config": tmp_path / "configs" / "costs.yaml",
        "feature_script": _write_feature_script(tmp_path),
    }


def _ignored(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        gate.rel(Path(artifact), tmp_path)
        for artifact in gate._expected_feature_artifacts(
            output_root=paths["feature_output_root"],
            reports_root=paths["feature_reports_root"],
        )
    ]


def _label_runner_report(status: str = label_runner.STATUS_DRY_RUN_READY) -> dict[str, object]:
    return {
        "summary": {
            "status": status,
            "commands_planned": 1,
            "commands_executed": 0,
            "expected_generated_output_count": 3,
            "ignored_expected_generated_output_count": 3,
            "unignored_expected_generated_output_count": 0,
            "existing_expected_generated_output_count": 0,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
            "failure_count": 0 if status == label_runner.STATUS_DRY_RUN_READY else 1,
        }
    }


def _completed_label_runner_report() -> dict[str, object]:
    return {
        "summary": {
            "status": label_runner.STATUS_NO_GO,
            "commands_planned": 1,
            "commands_executed": 0,
            "expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
            "ignored_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
            "unignored_expected_generated_output_count": 0,
            "existing_expected_generated_output_count": len(LABEL_EXPECTED_ARTIFACTS),
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
            "post_execution_staged_generated_path_count": 0,
            "failure_count": 2,
        },
        "planned_command": {
            "command_family": "phase3_label_build_exact_es2026_candidate",
            "command": "python -m scripts.phase3_labels.build_labels --markets ES --years 2026",
            "timeout_seconds": 900,
            "expected_generated_artifacts": LABEL_EXPECTED_ARTIFACTS,
        },
        "checks": [
            {
                "name": "planned_outputs_absent_before_execution",
                "status": "FAIL",
                "observed": LABEL_EXPECTED_ARTIFACTS,
                "expected": [],
                "detail": "The wrapper should not overwrite existing planned label outputs.",
            },
            {
                "name": "candidate_label_roots_empty_before_execution",
                "status": "FAIL",
                "observed": LABEL_EXPECTED_ARTIFACTS,
                "expected": [],
                "detail": "Candidate label output/report roots should not contain stale files.",
            },
        ],
    }


def _label_manifest_evidence(status: str = "PASS") -> dict[str, object]:
    if status != "PASS":
        return {
            "status": "FAIL",
            "path": "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
            "error": "missing JSON report",
        }
    return {
        "status": "PASS",
        "path": "reports/labels/local_trade_es2026_p1_candidate/label_manifest.json",
        "manifest_status": "PASS",
        "stage": "labels",
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "markets": ["ES"],
        "years": [2026],
        "failure_count": 0,
        "failures": [],
        "output_root_matches": True,
        "output_path": "data/labeled/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "output_exists": True,
        "manifest_output_hash": "a" * 64,
        "actual_output_hash": "a" * 64,
        "input_selection": {
            "profile_input_count": 33,
            "selected_input_count": 1,
            "requested_markets": ["ES"],
            "requested_years": [2026],
            "selected_markets": ["ES"],
            "selected_years": [2026],
        },
        "causal_base_manifest_gate_status": "PASS",
        "causal_base_manifest_gate_expected_market_year_count": 1,
        "output_row": {
            "market": "ES",
            "year": 2026,
            "status": "PASS",
            "failure_count": 0,
            "failures": [],
        },
    }


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    paths = _paths(tmp_path)
    if overrides.get("missing_year_flag"):
        paths["feature_script"] = _write_feature_script(tmp_path, missing_years=True)
    return gate.build_report(
        repo_root=tmp_path,
        **paths,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
        ignored_generated_paths=overrides.get("ignored_generated_paths", _ignored(paths, tmp_path)),
        label_runner_report=overrides.get("label_runner_report", _label_runner_report()),
        label_manifest_evidence=overrides.get("label_manifest_evidence", _label_manifest_evidence()),
    )


def test_ready_gate_defines_exact_phase4_feature_command(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 10
    assert report["summary"]["ignored_expected_generated_output_count"] == 10
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["feature_matrix_build_approved"] is False
    approval = report["approval_gate"]
    assert approval["approval_required"] is True
    assert approval["approval_token"] == gate.APPROVAL_TOKEN
    assert approval["maximum_scope"]["market_years"] == [{"market": "ES", "year": 2026}]
    assert approval["expected_ignored_artifacts"] == [
        "data/feature_matrices/local_trade_es2026_p1_candidate/ES/2026.parquet",
        "data/feature_matrices/local_trade_es2026_p1_candidate/excluded_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/feature_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/metadata_cols.json",
        "data/feature_matrices/local_trade_es2026_p1_candidate/target_cols.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_manifest.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/baseline_feature_report.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_audit.json",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_correlation_report.csv",
        "reports/features_baseline/local_trade_es2026_p1_candidate/feature_registry.json",
    ]
    command = approval["exact_command"]
    assert command.startswith("python -m scripts.phase4_features.build_baseline_features")
    assert "--profile tier_3_forward" in command
    assert "--input-root data/labeled/local_trade_es2026_p1_candidate" in command
    assert "--label-manifest reports/labels/local_trade_es2026_p1_candidate/label_manifest.json" in command
    assert "--markets ES" in command
    assert "--years 2026" in command
    assert "--shard-count" not in command
    assert "wfa_or_modeling" in approval["forbidden_actions_without_separate_approval"]


def test_missing_label_manifest_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, label_manifest_evidence=_label_manifest_evidence(status="FAIL"))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "label_manifest_exact_es2026_pass"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_label_wrapper_not_ready_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        label_runner_report=_label_runner_report(status=label_runner.STATUS_NO_GO),
    )

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "Resolve the guarded ES 2026 Phase 3 label wrapper no-go" in report["summary"][
        "recommended_next_action"
    ]
    assert any(
        check["name"] == "label_wrapper_guarded_or_completed"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_completed_label_artifacts_allow_feature_gate(tmp_path: Path) -> None:
    report = _build(tmp_path, label_runner_report=_completed_label_runner_report())

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["label_wrapper_status"] == label_runner.STATUS_NO_GO
    assert any(
        check["name"] == "label_wrapper_guarded_or_completed"
        for check in report["checks"]
        if check["status"] == "PASS"
    )
    assert report["approval_gate"]["approval_token"] == gate.APPROVAL_TOKEN


def test_missing_year_filter_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_year_flag=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "phase4_feature_cli_has_bounded_controls"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_expected_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _ignored(paths, tmp_path)[:-1]

    report = _build(tmp_path, ignored_generated_paths=ignored)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_feature_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_expected_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    output_path = paths["feature_output_root"] / "ES" / "2026.parquet"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"existing")

    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["existing_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_feature_artifacts_absent_before_execution"
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
