from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.phase1A_download.download_databento_raw import DownloadTask, build_raw_file_manifest
from scripts.validation import build_local_trade_es2026_p1_optional_archive_availability as availability


def _archive_path(tmp_path: Path, schema: str) -> Path:
    return tmp_path / "data" / "dbn" / schema / "ES" / "2026" / "2026-01-01_2026-06-13.dbn.zst"


def _plan(tmp_path: Path, schema: str, *, output_path: str | None = None) -> dict[str, object]:
    archive_path = output_path or _archive_path(tmp_path, schema).relative_to(tmp_path).as_posix()
    return {
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
                "output_path": archive_path,
            }
        ],
    }


def _write_plans(tmp_path: Path, *, output_path: str | None = None) -> Path:
    root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    for schema in availability.TARGET_SCHEMAS:
        path = root / f"phase1a_{schema}" / "databento_download_plan_dry_run.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_plan(tmp_path, schema, output_path=output_path)), encoding="utf-8")
    return root


def _expected_plan_paths(reports_root: Path, tmp_path: Path) -> list[str]:
    return sorted(
        [
            (reports_root / "phase1a_statistics" / "databento_download_plan_dry_run.json")
            .relative_to(tmp_path)
            .as_posix(),
            (reports_root / "phase1a_status" / "databento_download_plan_dry_run.json")
            .relative_to(tmp_path)
            .as_posix(),
        ]
    )


def _expected_archive_artifact_paths(tmp_path: Path) -> list[str]:
    paths: list[str] = []
    for schema in availability.TARGET_SCHEMAS:
        archive_path = _archive_path(tmp_path, schema)
        paths.append(archive_path.relative_to(tmp_path).as_posix())
        paths.append(archive_path.with_name(f"{archive_path.name}.manifest.json").relative_to(tmp_path).as_posix())
    return sorted(paths)


def _ignored_paths(reports_root: Path, tmp_path: Path) -> list[str]:
    return sorted([*_expected_plan_paths(reports_root, tmp_path), *_expected_archive_artifact_paths(tmp_path)])


def _windows_extra(paths: list[str]) -> list[str]:
    return sorted([path.replace("/", "\\") for path in paths] + ["reports\\pipeline_audit\\future.json"])


def _write_archive_and_manifest(tmp_path: Path, schema: str, *, repo_relative_manifest_path: bool = False) -> None:
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
    if repo_relative_manifest_path:
        manifest["path"] = archive_path.relative_to(tmp_path).as_posix()
    archive_path.with_name(f"{archive_path.name}.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_missing_dry_run_plans_fail_closed(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=[],
    )

    assert report["summary"]["status"] == availability.STATUS_NO_GO
    assert report["summary"]["planned_archive_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["failure_names"] == [
        "dry_run_review_ready",
        "dry_run_plans_reloaded",
        "planned_archive_paths_under_data",
    ]
    assert any(
        check["name"] == "dry_run_review_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_reports_missing_optional_archives_without_approving_execution(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_ignored_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == availability.STATUS_READY
    assert report["summary"]["planned_archive_count"] == 2
    assert report["summary"]["planned_generated_artifact_count"] == 4
    assert report["summary"]["ignored_planned_generated_artifact_count"] == 4
    assert report["summary"]["unignored_planned_generated_artifact_count"] == 0
    assert report["summary"]["missing_archive_count"] == 2
    assert report["summary"]["all_optional_archives_reusable"] is False
    assert report["summary"]["provider_download_approved"] is False
    assert report["summary"]["cost_estimate_approved"] is False
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert {item["availability_status"] for item in report["availability_items"]} == {
        "LOCAL_ARCHIVE_MISSING"
    }


def test_filters_windows_style_ignored_archive_paths(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_windows_extra(_ignored_paths(reports_root, tmp_path)),
    )

    assert report["summary"]["status"] == availability.STATUS_READY
    assert report["summary"]["planned_generated_artifact_count"] == 4
    assert report["summary"]["ignored_planned_generated_artifact_count"] == 4
    assert report["summary"]["unignored_planned_generated_artifact_count"] == 0


def test_reports_reusable_archives_when_archive_manifests_are_valid(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)
    for schema in availability.TARGET_SCHEMAS:
        _write_archive_and_manifest(tmp_path, schema)

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_ignored_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == availability.STATUS_READY
    assert report["summary"]["local_archive_ready_count"] == 2
    assert report["summary"]["missing_archive_count"] == 0
    assert report["summary"]["invalid_manifest_count"] == 0
    assert report["summary"]["all_optional_archives_reusable"] is True
    assert {item["availability_status"] for item in report["availability_items"]} == {
        "LOCAL_ARCHIVE_AND_MANIFEST_READY"
    }


def test_reports_reusable_archives_with_repo_relative_manifest_paths(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)
    for schema in availability.TARGET_SCHEMAS:
        _write_archive_and_manifest(tmp_path, schema, repo_relative_manifest_path=True)

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_ignored_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == availability.STATUS_READY
    assert report["summary"]["local_archive_ready_count"] == 2
    assert report["summary"]["invalid_manifest_count"] == 0
    assert report["summary"]["all_optional_archives_reusable"] is True
    assert all(not item["manifest_failures"] for item in report["availability_items"])


def test_output_path_outside_data_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path, output_path="outside/ES_2026.dbn.zst")

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_plan_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == availability.STATUS_NO_GO
    assert any(
        check["name"] == "planned_archive_paths_under_data"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_planned_archives_fail_closed(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = availability.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_plan_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == availability.STATUS_NO_GO
    assert report["summary"]["planned_generated_artifact_count"] == 4
    assert report["summary"]["unignored_planned_generated_artifact_count"] == 4
    assert any(
        check["name"] == "planned_archive_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_plans_missing(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = availability.main(
        [
            "--repo-root",
            str(tmp_path),
            "--repair-reports-root",
            str(reports_root),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{availability.STAGE} status={availability.STATUS_NO_GO}" in output
    assert "failure_names=dry_run_review_ready,dry_run_plans_reloaded,planned_archive_paths_under_data" in output
    assert "Generate and review exact ES 2026 status/statistics dry-run plans" in output
    assert "generated_outputs=0" in output
    assert not reports_root.exists()
