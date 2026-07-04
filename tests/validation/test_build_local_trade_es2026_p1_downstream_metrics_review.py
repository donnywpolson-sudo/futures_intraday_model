from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_gate as gate
from scripts.validation import build_local_trade_es2026_p1_downstream_metrics_review as review
from scripts.validation import run_local_trade_es2026_p1_downstream_metrics_build as metrics_runner
from tests.validation import test_build_local_trade_es2026_p1_downstream_metrics_gate as gate_fixtures
from tests.validation import test_run_local_trade_es2026_p1_downstream_metrics_build as runner_fixtures


def _paths(tmp_path: Path) -> dict[str, Path]:
    return gate_fixtures._paths(tmp_path)


def _expected_artifacts(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return gate_fixtures._expected_metrics_artifacts(paths, tmp_path)


def _write_metrics_outputs(
    tmp_path: Path,
    paths: dict[str, Path],
    *,
    failure_count: int = 0,
    final_holdout_touched: bool = False,
) -> None:
    gate_report = gate_fixtures._build(tmp_path)
    command = str(gate_report["approval_gate"]["exact_command"])
    runner_fixtures._write_valid_metrics_outputs(
        tmp_path,
        metrics_runner._command_to_argv(command),
        failure_count=failure_count,
        final_holdout_touched=final_holdout_touched,
    )


def _build(
    tmp_path: Path,
    *,
    write_model_outputs: bool = True,
    write_metrics_outputs: bool = True,
    metrics_failure_count: int = 0,
    final_holdout_touched: bool = False,
    ignored_paths: list[str] | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    paths = _paths(tmp_path)
    if write_metrics_outputs:
        _write_metrics_outputs(
            tmp_path,
            paths,
            failure_count=metrics_failure_count,
            final_holdout_touched=final_holdout_touched,
        )
    elif write_model_outputs:
        gate_fixtures._write_model_outputs(paths, tmp_path)
    return review.build_report(
        repo_root=tmp_path,
        profile=gate.DEFAULT_PROFILE,
        matrix=gate.DEFAULT_MATRIX,
        run=gate.DEFAULT_RUN,
        feature_output_root=paths["feature_output_root"],
        wfa_split_reports_root=paths["wfa_split_reports_root"],
        predictions_root=paths["predictions_root"],
        model_reports_root=paths["model_reports_root"],
        metrics_root=paths["metrics_root"],
        model_selection_root=paths["model_selection_root"],
        phase8_root=paths["phase8_root"],
        profile_config=paths["profile_config"],
        models_config=paths["models_config"],
        costs_config=paths["costs_config"],
        max_folds=gate.DEFAULT_MAX_FOLDS,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else _expected_artifacts(paths, tmp_path),
    )


def test_valid_metrics_outputs_are_review_ready(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["model_output_status"] == "PASS"
    assert report["summary"]["metrics_output_status"] == "PASS"
    assert report["summary"]["expected_generated_output_count"] == 8
    assert report["summary"]["ignored_expected_generated_output_count"] == 8
    assert report["summary"]["existing_expected_generated_output_count"] == 8
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["phase8_metrics_approved"] is False
    assert report["summary"]["model_selection_approved"] is False
    assert report["summary"]["model_promotion_approved"] is False
    assert report["review_detail"]["selection_status"] == "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY"
    assert report["review_detail"]["alpha_used_final_holdout_for_tuning"] is False


def test_missing_metrics_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_metrics_outputs=False)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["model_output_status"] == "PASS"
    assert report["summary"]["metrics_output_status"] == "FAIL"
    assert report["summary"]["existing_expected_generated_output_count"] == 0
    assert any(
        check["name"] == "expected_metrics_artifacts_present_for_review"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_model_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_model_outputs=False, write_metrics_outputs=False)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["model_output_status"] == "FAIL"
    assert any(
        check["name"] == "phase6_model_outputs_exact_es2026_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_bad_metrics_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, final_holdout_touched=True)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["metrics_output_status"] == "FAIL"
    assert any(
        check["name"] == "phase8_metrics_outputs_valid"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_metrics_outputs_fail_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _expected_artifacts(paths, tmp_path)[:-1]

    report = _build(tmp_path, ignored_paths=ignored)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_metrics_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unexpected_metrics_output_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_metrics_outputs(tmp_path, paths)
    unexpected_path = paths["metrics_root"] / "extra.json"
    unexpected_path.write_text("{}", encoding="utf-8")

    report = review.build_report(
        repo_root=tmp_path,
        profile=gate.DEFAULT_PROFILE,
        matrix=gate.DEFAULT_MATRIX,
        run=gate.DEFAULT_RUN,
        feature_output_root=paths["feature_output_root"],
        wfa_split_reports_root=paths["wfa_split_reports_root"],
        predictions_root=paths["predictions_root"],
        model_reports_root=paths["model_reports_root"],
        metrics_root=paths["metrics_root"],
        model_selection_root=paths["model_selection_root"],
        phase8_root=paths["phase8_root"],
        profile_config=paths["profile_config"],
        models_config=paths["models_config"],
        costs_config=paths["costs_config"],
        max_folds=gate.DEFAULT_MAX_FOLDS,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_artifacts(paths, tmp_path),
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["unexpected_generated_output_count"] == 1
    assert any(
        check["name"] == "unexpected_phase8_outputs_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_review_packet_is_compact(tmp_path: Path) -> None:
    report = _build(tmp_path)
    packet = review.review_packet(report)

    assert packet["stage"] == review.STAGE
    assert packet["status"] == review.STATUS_READY
    assert packet["approval_gate"] == {}
    assert packet["non_approval"]["commands_executed"] == 0
    assert packet["non_approval"]["promotion_or_freeze_approved"] is False
    assert packet["non_approval"]["proof_scan_approved"] is False
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
    assert packet["model_promotion_allowed"] is False


def test_cli_missing_outputs_returns_no_go(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = review.main(["--repo-root", str(tmp_path), "--print-review-json"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{review.STAGE} status={review.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
