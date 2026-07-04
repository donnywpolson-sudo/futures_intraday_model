from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.phase1A_download.download_databento_raw import DownloadTask, build_raw_file_manifest
from scripts.validation import build_local_trade_es2026_p1_candidate_conversion_plan as conversion_plan
from tests.validation import test_build_local_trade_es2026_p1_repair_plan as repair_fixtures
from tests.validation import test_build_local_trade_es2026_p1_optional_archive_availability as availability_fixtures


def _archive_path(tmp_path: Path, schema: str) -> Path:
    return tmp_path / "data" / "dbn" / schema / "ES" / "2026" / "2026-01-01_2026-06-13.dbn.zst"


def _write_plans(tmp_path: Path) -> Path:
    root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    for schema in ("statistics", "status"):
        path = root / f"phase1a_{schema}" / "databento_download_plan_dry_run.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "run_kind": "dry_run",
                    "mode": "download-dbn",
                    "schema": schema,
                    "schemas": [schema],
                    "start": "2026-01-01",
                    "end": "2026-06-13",
                    "universe": "custom",
                    "products": ["ES"],
                    "product_count": 1,
                    "task_count": 1,
                    "tasks": [
                        {
                            "dataset": "GLBX.MDP3",
                            "product": "ES",
                            "year": 2026,
                            "schema": schema,
                            "start": "2026-01-01",
                            "end": "2026-06-13",
                            "symbol": "ES.FUT",
                            "stype_in": "parent",
                            "stype_out": "instrument_id",
                            "output_path": _archive_path(tmp_path, schema).relative_to(tmp_path).as_posix(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return root


def _write_archive_and_manifest(tmp_path: Path, schema: str) -> None:
    archive_path = _archive_path(tmp_path, schema)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(f"{schema} archive".encode("utf-8"))
    task = DownloadTask(
        dataset="GLBX.MDP3",
        product="ES",
        year=2026,
        start="2026-01-01",
        end="2026-06-13",
        symbol="ES.FUT",
        output_path=archive_path.as_posix(),
        schema=schema,
        raw_format="dbn-zstd",
    )
    manifest = build_raw_file_manifest(task, archive_path, job_id="test", request_status="downloaded")
    archive_path.with_name(f"{archive_path.name}.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def _candidate_expected_output_paths(tmp_path: Path) -> list[str]:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    return sorted(
        [
            (tmp_path / "data" / "raw_es2026_candidate" / "ES" / "2026.parquet")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_conversion" / "databento_convert_results.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_conversion" / "raw_ingest_manifest.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_conversion" / "raw_parquet_manifest.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_optional_schema_audit" / "ES_2026_optional_schema_audit.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "candidate_raw_optional_schema_audit" / "ES_2026_optional_schema_audit.md")
            .relative_to(tmp_path)
            .as_posix(),
        ]
    )


def _ignored_paths(tmp_path: Path, reports_root: Path, *, include_candidate_outputs: bool = True) -> list[str]:
    paths = availability_fixtures._ignored_paths(reports_root, tmp_path)
    if include_candidate_outputs:
        paths.extend(_candidate_expected_output_paths(tmp_path))
    return sorted(paths)


def _windows_extra(paths: list[str]) -> list[str]:
    return sorted([path.replace("/", "\\") for path in paths] + ["reports\\pipeline_audit\\future.json"])


def _build(
    tmp_path: Path,
    *,
    write_plans: bool = False,
    write_archives: bool = False,
    staged: list[str] | None = None,
    include_candidate_outputs_in_ignored: bool = True,
    ignored_paths: list[str] | None = None,
) -> dict[str, object]:
    work_order, drilldown, checkpoint = repair_fixtures._write_reports(tmp_path)
    repair_reports_root = (
        _write_plans(tmp_path)
        if write_plans
        else tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    )
    if write_archives:
        for schema in ("statistics", "status"):
            _write_archive_and_manifest(tmp_path, schema)
    return conversion_plan.build_report(
        repo_root=tmp_path,
        work_order_report=work_order,
        drilldown_report=drilldown,
        checkpoint_jsonl=checkpoint,
        repair_reports_root=repair_reports_root,
        candidate_raw_root=tmp_path / "data" / "raw_es2026_candidate",
        output_root=tmp_path / "data" / "causal_es2026_candidate",
        raw_alignment_report=repair_reports_root / "alignment.json",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        ignored_generated_paths=ignored_paths
        if ignored_paths is not None
        else _ignored_paths(
            tmp_path,
            repair_reports_root,
            include_candidate_outputs=include_candidate_outputs_in_ignored,
        ),
    )


def test_missing_dry_run_plans_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == conversion_plan.STATUS_NO_GO
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert any(
        check["name"] == "optional_archives_reusable"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_local_optional_archives_block_conversion_plan(tmp_path: Path) -> None:
    report = _build(tmp_path, write_plans=True)

    assert report["summary"]["status"] == conversion_plan.STATUS_NO_GO
    assert report["availability_summary"]["status"] == "REVIEW_READY_ES2026_P1_OPTIONAL_ARCHIVE_AVAILABILITY"
    assert report["availability_summary"]["missing_archive_count"] == 2
    assert report["summary"]["selected_command_family_count"] == 2
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False


def test_valid_local_optional_archives_make_conversion_plan_review_ready(tmp_path: Path) -> None:
    report = _build(tmp_path, write_plans=True, write_archives=True)

    assert report["summary"]["status"] == conversion_plan.STATUS_READY
    assert report["summary"]["selected_command_family_count"] == 2
    assert report["summary"]["approval_required_command_count"] == 2
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert {family["name"] for family in report["command_families"]} == {
        "candidate_raw_convert_with_required_optional_enrichment",
        "candidate_raw_optional_schema_audit",
    }


def test_filters_windows_style_ignored_candidate_outputs(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    report = _build(
        tmp_path,
        write_plans=True,
        write_archives=True,
        ignored_paths=_windows_extra(_ignored_paths(tmp_path, reports_root)),
    )

    assert report["summary"]["status"] == conversion_plan.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["ignored_expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 0


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, write_plans=True, write_archives=True, staged=["reports/generated.json"])

    assert report["summary"]["status"] == conversion_plan.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_candidate_outputs_fail_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        write_plans=True,
        write_archives=True,
        include_candidate_outputs_in_ignored=False,
    )

    assert report["summary"]["status"] == conversion_plan.STATUS_NO_GO
    assert report["summary"]["expected_generated_output_count"] == 6
    assert report["summary"]["unignored_expected_generated_output_count"] == 6
    assert any(
        check["name"] == "candidate_expected_outputs_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_plans_missing(tmp_path: Path, capsys) -> None:
    work_order, drilldown, checkpoint = repair_fixtures._write_reports(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = conversion_plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--work-order-report",
            str(work_order),
            "--drilldown-report",
            str(drilldown),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--repair-reports-root",
            str(reports_root),
            "--candidate-raw-root",
            str(tmp_path / "data" / "raw_es2026_candidate"),
            "--output-root",
            str(tmp_path / "data" / "causal_es2026_candidate"),
            "--raw-alignment-report",
            str(reports_root / "alignment.json"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{conversion_plan.STAGE} status={conversion_plan.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
    assert not reports_root.exists()
