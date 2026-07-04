from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import run_local_trade_es2026_p1_accepted_warning_review as runner
from scripts.validation import run_local_trade_es2026_p1_repair_diagnostic as repair_runner


def _write_diagnostic(
    tmp_path: Path,
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
        f"2026-03-18T00:0{index}:00+00:00"
        for index in range(statistics_issue_rows)
    ]
    payload = {
        "summary": {
            "stage": repair_runner.STAGE,
            "status": status,
            "profile": profile,
            "market": market,
            "year": year,
            "recommended_disposition": disposition,
        },
        "candidate_raw_metrics": {
            "data_quality_degraded_or_unavailable_rows": degraded_rows,
            "statistics_issue_rows": statistics_issue_rows,
            "status_issue_rows": status_issue_rows,
            "statistics_issue_sample_timestamps": timestamps,
        },
        "optional_schema_audit_summary": {
            "status": "PASS",
            "status_metrics": {
                "status_missing_rows": 0,
                "status_stale_rows": 0,
            },
            "statistics_metrics": {
                "statistics_missing_rows": statistics_issue_rows,
                "statistics_stale_rows": statistics_issue_rows,
            },
        },
        "conversion_summary": {
            "status": "ok",
            "optional_schema_policy": "require",
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
            / "accepted_warning_review"
            / "review.json"
        ),
        "output_md": (
            tmp_path
            / "reports"
            / "pipeline_audit"
            / "accepted_warning_review"
            / "review.md"
        ),
    }


def _ignored_outputs(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        paths["output_json"].relative_to(tmp_path).as_posix(),
        paths["output_md"].relative_to(tmp_path).as_posix(),
    ]


def _build(
    tmp_path: Path,
    *,
    ignored_paths: list[str] | None = None,
    staged: list[str] | None = None,
    **diagnostic_kwargs,
) -> dict[str, object]:
    paths = _paths(tmp_path)
    return runner.build_report(
        repo_root=tmp_path,
        input_diagnostic=_write_diagnostic(tmp_path, **diagnostic_kwargs),
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=(
            ignored_paths if ignored_paths is not None else _ignored_outputs(paths, tmp_path)
        ),
        **paths,
    )


def test_review_reports_packet_not_ready_for_current_statistics_gap(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_READY
    assert report["summary"]["criteria_status"] == runner.CRITERIA_STATUS_PACKET_NOT_READY
    assert report["summary"]["accepted_warning_packet_should_be_separately_approved"] is False
    assert report["summary"]["further_statistics_repair_needed"] is True
    assert report["summary"]["es2026_remains_fail_closed"] is True
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False
    assert report["non_approval"]["accepted_warning_packet_written"] is False
    assert report["non_approval"]["readiness_rerun"] is False
    assert report["non_approval"]["data_written"] is False

    criteria = {item["name"]: item["status"] for item in report["criteria"]}
    assert criteria["exact_statistics_issue_rows_identified"] == runner.CRITERIA_MET
    assert criteria["no_candidate_raw_degraded_or_status_issue_rows"] == runner.CRITERIA_MET
    assert criteria["optional_audit_confirms_statistics_gap_only"] == runner.CRITERIA_MET
    assert (
        criteria["candidate_conversion_preserved_required_optional_schemas"]
        == runner.CRITERIA_MET
    )
    assert (
        criteria["current_phase2_exception_schema_supports_statistics_warning"]
        == runner.CRITERIA_MET
    )
    assert criteria["exact_phase2_statistics_warning_available"] == runner.CRITERIA_NOT_MET


def test_wrong_scope_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, market="NQ")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
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
    diagnostic = _write_diagnostic(tmp_path)
    paths = _paths(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--input-diagnostic",
            str(diagnostic),
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
    assert f"criteria_status={runner.CRITERIA_STATUS_PACKET_NOT_READY}" in output
    assert "packet_approval_recommended=False" in output
    assert "generated_outputs=2" in output
    assert paths["output_md"].exists()
    assert payload["summary"]["generated_output_count"] == 2
    assert payload["summary"]["post_execution_staged_generated_path_count"] == 0


def test_cli_no_go_writes_no_reports_when_preconditions_fail(
    tmp_path: Path,
    capsys,
) -> None:
    diagnostic = _write_diagnostic(
        tmp_path,
        disposition=repair_runner.DISPOSITION_REMAIN_FAIL_CLOSED,
    )
    paths = _paths(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--input-diagnostic",
            str(diagnostic),
            "--output-json",
            str(paths["output_json"]),
            "--output-md",
            str(paths["output_md"]),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{runner.STAGE} status={runner.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
    assert not paths["output_json"].exists()
    assert not paths["output_md"].exists()
