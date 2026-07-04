from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_dry_run_review as review


def _plan(schema: str, *, market: str = "ES", year: int = 2026) -> dict[str, object]:
    return {
        "run_kind": "dry_run",
        "mode": "download-dbn",
        "schema": schema,
        "schemas": [schema],
        "start": "2026-01-01",
        "end": "2026-06-13",
        "universe": "custom",
        "products": [market],
        "product_count": 1,
        "task_count": 1,
        "tasks": [
            {
                "product": market,
                "year": year,
                "schema": schema,
                "start": "2026-01-01",
                "end": "2026-06-13",
            }
        ],
    }


def _write_plans(
    tmp_path: Path,
    *,
    market: str = "ES",
    year: int = 2026,
) -> Path:
    root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    for schema in ("statistics", "status"):
        path = root / f"phase1a_{schema}" / "databento_download_plan_dry_run.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_plan(schema, market=market, year=year)), encoding="utf-8")
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


def _windows_extra(paths: list[str]) -> list[str]:
    return sorted([path.replace("/", "\\") for path in paths] + ["reports\\pipeline_audit\\future.json"])


def test_reviews_exact_es2026_status_statistics_dry_run_plans(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_plan_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["readable_plan_count"] == 2
    assert report["summary"]["ignored_plan_count"] == 2
    assert report["summary"]["unignored_plan_count"] == 0
    assert report["summary"]["review_item_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["provider_download_approved"] is False
    assert report["summary"]["candidate_raw_write_approved"] is False
    assert {item["schema"] for item in report["review_items"]} == {"statistics", "status"}
    assert {item["market"] for item in report["review_items"]} == {"ES"}
    assert {item["year"] for item in report["review_items"]} == {2026}


def test_review_filters_windows_style_ignored_plan_paths(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_windows_extra(_expected_plan_paths(reports_root, tmp_path)),
    )

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["ignored_plan_count"] == 2
    assert report["summary"]["unignored_plan_count"] == 0


def test_missing_plans_fail_closed(tmp_path: Path) -> None:
    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=[],
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["review_item_count"] == 0
    assert any(
        check["name"] == "expected_dry_run_plans_readable"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_wrong_scope_fails_closed(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path, market="NQ", year=2026)

    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=_expected_plan_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert any(
        check["name"] == "dry_run_plans_exact_es2026_scope"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=["reports/generated.json"],
        ignored_generated_paths=_expected_plan_paths(reports_root, tmp_path),
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_generated_plans_fail_closed(tmp_path: Path) -> None:
    reports_root = _write_plans(tmp_path)

    report = review.build_report(
        repo_root=tmp_path,
        repair_reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        ignored_generated_paths=[],
    )

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["ignored_plan_count"] == 0
    assert report["summary"]["unignored_plan_count"] == 2
    assert any(
        check["name"] == "dry_run_plans_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_no_go_writes_no_reports_when_plans_missing(tmp_path: Path, capsys) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "repair_plan_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = review.main(
        [
            "--repo-root",
            str(tmp_path),
            "--repair-reports-root",
            str(reports_root),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert f"{review.STAGE} status={review.STATUS_NO_GO}" in output
    assert "generated_outputs=0" in output
    assert not reports_root.exists()
