from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from scripts.validation import run_local_trade_es2026_p1_repair_diagnostic as runner


def _candidate_raw_path(tmp_path: Path, market: str = "ES", year: int = 2026) -> Path:
    return tmp_path / "data" / "raw_es2026_candidate" / market / f"{year}.parquet"


def _write_candidate_raw(
    tmp_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
    degraded_rows: int = 0,
    statistics_issue_rows: int = 6,
) -> Path:
    path = _candidate_raw_path(tmp_path, market, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = pd.date_range("2026-03-18T13:30:00Z", periods=10, freq="min")
    frame = pd.DataFrame(
        {
            "ts_event": timestamps,
            "data_quality_status": [
                "degraded" if index < degraded_rows else "available"
                for index in range(len(timestamps))
            ],
            "data_quality_degraded": [
                index < degraded_rows for index in range(len(timestamps))
            ],
            "statistics_missing": [
                index < statistics_issue_rows for index in range(len(timestamps))
            ],
            "statistics_stale": [
                index < statistics_issue_rows for index in range(len(timestamps))
            ],
            "status_missing": [False] * len(timestamps),
            "status_stale": [False] * len(timestamps),
            "status_source_file": ["data/dbn/status/ES/2026/archive.dbn.zst"] * len(timestamps),
            "stat_settlement_price_source_file": [
                "data/dbn/statistics/ES/2026/archive.dbn.zst"
            ]
            * len(timestamps),
        }
    )
    frame.to_parquet(path, index=False)
    return path


def _write_work_order(tmp_path: Path, *, market: str = "ES", year: int = 2026) -> Path:
    path = tmp_path / "reports" / "work_order.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "phase2_repair_work_order",
                "status": "FAIL",
                "work_orders": [
                    {
                        "market": market,
                        "year": year,
                        "priority": "P1",
                        "work_order_actions": [
                            "repair_status_statistics_enrichment",
                            "review_degraded_raw_quality",
                            "exclude_only_if_explicitly_approved",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_raw_quality(
    tmp_path: Path,
    candidate_raw_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
    status: str = "FAIL",
) -> Path:
    path = tmp_path / "reports" / "raw_quality.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "phase2_readiness_raw_drilldown",
                "status": status,
                "selected_market_years": [{"market": market, "year": year}],
                "selected_market_year_count": 1,
                "drilldowns": [
                    {
                        "market": market,
                        "year": year,
                        "raw_path": candidate_raw_path.as_posix(),
                        "raw_read_status": "PASS",
                        "top_blocker_reason": (
                            "degraded threshold breached: rows_pct=1.74227 bars=2760 sessions=3"
                        ),
                        "degraded_bar_rows": 2760,
                        "degraded_rows_pct": 1.74227,
                        "degraded_session_rows": 3,
                        "statistics_enrichment_missing_rows": 6,
                        "statistics_enrichment_stale_rows": 6,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_optional_audit(
    tmp_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
    status: str = "PASS",
) -> Path:
    path = tmp_path / "reports" / "optional_schema_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "raw_enriched_optional_schema_audit",
                "status": status,
                "verdicts": {
                    "optional_status_readiness": "PASS",
                    "optional_statistics_readiness": "PASS",
                },
                "files": [
                    {
                        "market": market,
                        "year": year,
                        "status": status,
                        "status_metrics": {
                            "status_missing_rows": 0,
                            "status_stale_rows": 0,
                        },
                        "statistics_metrics": {
                            "statistics_missing_rows": 6,
                            "statistics_stale_rows": 6,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_conversion(
    tmp_path: Path,
    candidate_raw_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
) -> Path:
    path = tmp_path / "reports" / "conversion.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "status": "ok",
                    "market": market,
                    "year": year,
                    "output_path": candidate_raw_path.resolve().as_posix(),
                    "optional_schema_policy": "require",
                    "optional_schemas": ["status", "statistics"],
                    "optional_schema_match_summary": {
                        "status": {"missing_rows": 0},
                        "statistics": {"missing_rows": 6, "matched_rows": 4},
                    },
                    "data_quality_status_counts": {"available": 10},
                    "degraded_bar_count": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def _setup(
    tmp_path: Path,
    *,
    raw_quality_status: str = "FAIL",
    raw_quality_market: str = "ES",
    raw_quality_year: int = 2026,
    work_order_market: str = "ES",
    degraded_rows: int = 0,
    statistics_issue_rows: int = 6,
) -> dict[str, Path]:
    candidate_raw_path = _write_candidate_raw(
        tmp_path,
        degraded_rows=degraded_rows,
        statistics_issue_rows=statistics_issue_rows,
    )
    return {
        "work_order_report": _write_work_order(tmp_path, market=work_order_market),
        "raw_quality_report": _write_raw_quality(
            tmp_path,
            candidate_raw_path,
            market=raw_quality_market,
            year=raw_quality_year,
            status=raw_quality_status,
        ),
        "optional_schema_audit": _write_optional_audit(tmp_path),
        "conversion_report": _write_conversion(tmp_path, candidate_raw_path),
        "candidate_raw_root": candidate_raw_path.parents[1],
        "candidate_raw_path": candidate_raw_path,
        "output_json": tmp_path / "reports" / "pipeline_audit" / "diag" / "diagnostic.json",
        "output_md": tmp_path / "reports" / "pipeline_audit" / "diag" / "diagnostic.md",
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
    **setup_kwargs,
) -> dict[str, object]:
    paths = _setup(tmp_path, **setup_kwargs)
    return runner.build_report(
        repo_root=tmp_path,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths if ignored_paths is not None else _ignored_outputs(paths, tmp_path),
        **paths,
    )


def test_recommends_accepted_warning_review_for_statistics_gap_only(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == runner.STATUS_READY
    assert report["summary"]["recommended_disposition"] == runner.DISPOSITION_ACCEPTED_WARNING_REVIEW
    assert report["diagnostic_disposition"]["candidate_raw_repair_or_rebuild_needed"] is False
    assert report["diagnostic_disposition"]["accepted_warning_review_needed"] is True
    assert report["diagnostic_disposition"]["remain_fail_closed"] is True
    assert report["candidate_raw_metrics"]["data_quality_degraded_or_unavailable_rows"] == 0
    assert report["candidate_raw_metrics"]["statistics_issue_rows"] == 6
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_rerun_approved"] is False


def test_candidate_raw_degraded_rows_require_repair_or_rebuild(tmp_path: Path) -> None:
    report = _build(tmp_path, degraded_rows=2)

    assert report["summary"]["status"] == runner.STATUS_READY
    assert report["summary"]["recommended_disposition"] == runner.DISPOSITION_CANDIDATE_RAW_REPAIR
    assert report["diagnostic_disposition"]["candidate_raw_repair_or_rebuild_needed"] is True
    assert report["candidate_raw_metrics"]["data_quality_degraded_or_unavailable_rows"] == 2


def test_non_fail_raw_quality_fails_closed_without_writing(tmp_path: Path) -> None:
    report = _build(tmp_path, raw_quality_status="PASS")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert any(
        check["name"] == "raw_quality_fail_closed_blocker_present"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_wrong_scope_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, raw_quality_market="NQ")

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "raw_quality_exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_candidate_raw_root_must_contain_only_es2026(tmp_path: Path) -> None:
    paths = _setup(tmp_path)
    _write_candidate_raw(tmp_path, market="NQ", year=2026)

    report = runner.build_report(
        repo_root=tmp_path,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_ignored_outputs(paths, tmp_path),
        **paths,
    )

    assert report["summary"]["status"] == runner.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_raw_root_exact_target_only"
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


def test_cli_writes_ignored_reports_and_concise_output(tmp_path: Path, capsys) -> None:
    paths = _setup(tmp_path)
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(paths["work_order_report"]),
            "--raw-quality-report",
            str(paths["raw_quality_report"]),
            "--optional-schema-audit",
            str(paths["optional_schema_audit"]),
            "--conversion-report",
            str(paths["conversion_report"]),
            "--candidate-raw-root",
            str(paths["candidate_raw_root"]),
            "--candidate-raw-path",
            str(paths["candidate_raw_path"]),
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
    assert f"recommended_disposition={runner.DISPOSITION_ACCEPTED_WARNING_REVIEW}" in output
    assert "generated_outputs=2" in output
    assert paths["output_md"].exists()
    assert payload["summary"]["generated_output_count"] == 2
    assert payload["summary"]["post_execution_staged_generated_path_count"] == 0


def test_cli_no_go_writes_no_reports_when_preconditions_fail(tmp_path: Path, capsys) -> None:
    paths = _setup(tmp_path, raw_quality_status="PASS")
    (tmp_path / ".gitignore").write_text("reports/\ndata/\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = runner.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(paths["work_order_report"]),
            "--raw-quality-report",
            str(paths["raw_quality_report"]),
            "--optional-schema-audit",
            str(paths["optional_schema_audit"]),
            "--conversion-report",
            str(paths["conversion_report"]),
            "--candidate-raw-root",
            str(paths["candidate_raw_root"]),
            "--candidate-raw-path",
            str(paths["candidate_raw_path"]),
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
