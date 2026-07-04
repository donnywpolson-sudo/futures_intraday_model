from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from scripts.validation import run_local_trade_es2026_p1_readiness_warning_evidence as runner
from scripts.validation import run_local_trade_es2026_p1_repair_diagnostic as repair_runner


def _candidate_raw_path(tmp_path: Path, market: str = "ES", year: int = 2026) -> Path:
    return tmp_path / "data" / "raw_es2026_p1_repair_candidate" / market / f"{year}.parquet"


def _write_candidate_raw(tmp_path: Path) -> Path:
    path = _candidate_raw_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.date_range("2026-03-18T13:30:00Z", periods=6, freq="min")
    rows = []
    for index, ts_event in enumerate(timestamps):
        close = 100.5 + index
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH6",
                "ts_event": ts_event,
                "open": close - 0.5,
                "high": close + 0.5,
                "low": close - 1.0,
                "close": close,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
                "status_is_trading": True,
                "status_is_quoting": True,
                "status_missing": False,
                "status_stale": False,
                "statistics_missing": True,
                "statistics_stale": True,
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def _write_profile_config(tmp_path: Path) -> Path:
    path = tmp_path / "configs" / "alpha_tiered.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "defaults:",
                "  years: [2026]",
                "  max_synthetic_gap_minutes: 120",
                "  max_synthetic_rows_pct: 100.0",
                "  max_degraded_rows_pct: 1.0",
                "  max_roll_window_rows_pct: 100.0",
                "  require_roll_metadata_for_profiles: []",
                "profiles:",
                "  tier_3_forward:",
                "    markets: [ES]",
                "    years: [2026]",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_diagnostic(
    tmp_path: Path,
    candidate_raw_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
    profile: str = "tier_3_forward",
    status: str = repair_runner.STATUS_READY,
    disposition: str = repair_runner.DISPOSITION_ACCEPTED_WARNING_REVIEW,
    statistics_issue_rows: int = 6,
    status_issue_rows: int = 0,
    degraded_rows: int = 0,
) -> Path:
    path = tmp_path / "reports" / "repair_diagnostic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = [
        f"2026-03-18T13:3{index}:00+00:00"
        for index in range(statistics_issue_rows)
    ]
    payload = {
        "summary": {
            "stage": repair_runner.STAGE,
            "status": status,
            "profile": profile,
            "market": market,
            "year": year,
            "candidate_raw_path": candidate_raw_path.relative_to(tmp_path).as_posix(),
            "recommended_disposition": disposition,
        },
        "candidate_raw_metrics": {
            "data_quality_degraded_or_unavailable_rows": degraded_rows,
            "statistics_issue_rows": statistics_issue_rows,
            "status_issue_rows": status_issue_rows,
            "statistics_issue_sample_timestamps": timestamps,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "output_json": (
            tmp_path
            / "reports"
            / "pipeline_audit"
            / "readiness_warning_evidence"
            / "review.json"
        ),
        "output_md": (
            tmp_path
            / "reports"
            / "pipeline_audit"
            / "readiness_warning_evidence"
            / "review.md"
        ),
    }


def _ignored_outputs(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        paths["output_json"].relative_to(tmp_path).as_posix(),
        paths["output_md"].relative_to(tmp_path).as_posix(),
    ]


def _exact_phase2_warning_evidence() -> dict[str, object]:
    return {
        "collection_error": None,
        "profile": runner.TARGET_PROFILE,
        "market": runner.TARGET_MARKET,
        "year": runner.TARGET_YEAR,
        "input_path": "data/raw_es2026_p1_repair_candidate/ES/2026.parquet",
        "non_written_output_path": "reports/non_written/ES/2026.parquet",
        "write_output": False,
        "status": "WARN",
        "warnings": [runner.EXPECTED_PHASE2_STATISTICS_WARNING],
        "failures": [],
        "warning_count": 1,
        "failure_count": 0,
        "raw_rows": 6,
        "output_rows": 6,
        "synthetic_rows": 0,
        "synthetic_gap_threshold_breached": False,
        "roll_window_threshold_breached": False,
        "degraded_threshold_breached": False,
        "roll_maturity_backstep_count": 0,
        "degraded_bar_rows": 0,
        "degraded_session_rows": 0,
        "status_enrichment_missing_rows": 0,
        "status_enrichment_stale_rows": 0,
        "statistics_enrichment_missing_rows": 6,
        "statistics_enrichment_stale_rows": 6,
    }


def _build(
    tmp_path: Path,
    *,
    ignored_paths: list[str] | None = None,
    staged: list[str] | None = None,
    phase2_warning_evidence: dict[str, object] | None = None,
    **diagnostic_kwargs,
) -> dict[str, object]:
    candidate_raw_path = _write_candidate_raw(tmp_path)
    paths = _paths(tmp_path)
    return runner.build_report(
        repo_root=tmp_path,
        input_diagnostic=_write_diagnostic(tmp_path, candidate_raw_path, **diagnostic_kwargs),
        candidate_raw_path=candidate_raw_path,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=(
            ignored_paths if ignored_paths is not None else _ignored_outputs(paths, tmp_path)
        ),
        phase2_warning_evidence=phase2_warning_evidence or _exact_phase2_warning_evidence(),
        **paths,
    )


def test_exact_warning_evidence_allows_separate_packet_preparation(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_READY
    assert report["summary"]["evidence_status"] == runner.EVIDENCE_PACKET_READY
    assert (
        report["summary"]["accepted_warning_packet_can_be_prepared_with_separate_approval"]
        is True
    )
    assert report["summary"]["es2026_remains_fail_closed"] is True
    assert report["summary"]["generated_output_count"] == 0
    assert report["non_approval"]["accepted_warning_packet_written"] is False
    assert report["non_approval"]["data_written"] is False
    assert report["non_approval"]["candidate_raw_rewritten"] is False

    criteria = {item["name"]: item["status"] for item in report["evidence_criteria"]}
    assert set(criteria.values()) == {"MET"}


def test_wrong_scope_fails_closed_without_collecting_evidence(tmp_path: Path) -> None:
    report = _build(tmp_path, market="NQ")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert report["phase2_warning_evidence"]["status"] == "NOT_RUN"
    assert any(
        check["name"] == "exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_non_accepted_warning_diagnostic_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, disposition=repair_runner.DISPOSITION_REMAIN_FAIL_CLOSED)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert any(
        check["name"] == "repair_diagnostic_ready_for_accepted_warning_review"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_must_be_limited_to_six_statistics_rows(tmp_path: Path) -> None:
    report = _build(tmp_path, statistics_issue_rows=7)

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "limited_to_six_statistics_rows"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_exact_warning_keeps_es2026_fail_closed_for_repair(tmp_path: Path) -> None:
    evidence = _exact_phase2_warning_evidence()
    evidence["warnings"] = []
    evidence["status"] = "PASS"
    report = _build(tmp_path, phase2_warning_evidence=evidence)

    assert report["summary"]["status"] == runner.STATUS_READY
    assert report["summary"]["evidence_status"] == runner.EVIDENCE_REPAIR_REQUIRED
    assert (
        report["summary"]["accepted_warning_packet_can_be_prepared_with_separate_approval"]
        is False
    )
    assert report["summary"]["further_statistics_repair_needed"] is True
    assert report["summary"]["es2026_remains_fail_closed"] is True
    criteria = {item["name"]: item["status"] for item in report["evidence_criteria"]}
    assert criteria["exact_current_statistics_warning_only"] == "NOT_MET"


def test_unignored_report_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, ignored_paths=[])

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["unignored_planned_generated_output_count"] == 2
    assert any(
        check["name"] == "planned_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/generated.json"])

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_writes_ignored_reports_and_concise_output(tmp_path: Path, capsys) -> None:
    candidate_raw_path = _write_candidate_raw(tmp_path)
    diagnostic = _write_diagnostic(tmp_path, candidate_raw_path)
    profile_config = _write_profile_config(tmp_path)
    paths = _paths(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--input-diagnostic",
            str(diagnostic),
            "--candidate-raw-path",
            str(candidate_raw_path),
            "--profile-config",
            str(profile_config),
            "--session-config",
            str((Path.cwd() / runner.phase2_causal_base.DEFAULT_SESSION_CONFIG).resolve()),
            "--output-json",
            str(paths["output_json"]),
            "--output-md",
            str(paths["output_md"]),
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(paths["output_json"].read_text(encoding="utf-8"))
    assert exit_code == 0
    assert f"{runner.STAGE} status={runner.STATUS_READY}" in output
    assert f"evidence_status={runner.EVIDENCE_PACKET_READY}" in output
    assert "packet_ready=True" in output
    assert "generated_outputs=2" in output
    assert paths["output_md"].exists()
    assert payload["summary"]["generated_output_count"] == 2
    assert payload["summary"]["post_execution_staged_generated_path_count"] == 0
    assert payload["phase2_warning_evidence"]["write_output"] is False
    assert payload["phase2_warning_evidence"]["warnings"] == [
        runner.EXPECTED_PHASE2_STATISTICS_WARNING
    ]


def test_cli_no_go_writes_no_reports_when_preconditions_fail(
    tmp_path: Path,
    capsys,
) -> None:
    candidate_raw_path = _write_candidate_raw(tmp_path)
    diagnostic = _write_diagnostic(
        tmp_path,
        candidate_raw_path,
        disposition=repair_runner.DISPOSITION_REMAIN_FAIL_CLOSED,
    )
    profile_config = _write_profile_config(tmp_path)
    paths = _paths(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--input-diagnostic",
            str(diagnostic),
            "--candidate-raw-path",
            str(candidate_raw_path),
            "--profile-config",
            str(profile_config),
            "--session-config",
            str((Path.cwd() / runner.phase2_causal_base.DEFAULT_SESSION_CONFIG).resolve()),
            "--output-json",
            str(paths["output_json"]),
            "--output-md",
            str(paths["output_md"]),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{runner.STAGE} status={runner.STATUS_NO_GO}" in output
    assert "failure_count=1" in output
    assert not paths["output_json"].exists()
    assert not paths["output_md"].exists()
