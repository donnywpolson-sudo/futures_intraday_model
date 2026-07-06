from __future__ import annotations

from pathlib import Path

from scripts import check_git_hygiene


def collect(
    tmp_path: Path,
    *,
    tracked: set[str] | None = None,
    staged: set[str] | None = None,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    return check_git_hygiene.collect_findings(
        tmp_path,
        tracked=tracked or set(),
        staged=staged or set(),
    )


def test_grandfathers_existing_tracked_reports(tmp_path: Path) -> None:
    large_files, forbidden_files = collect(
        tmp_path,
        tracked={"reports/data_manifest/master_data_health_summary.md"},
    )

    assert large_files == []
    assert forbidden_files == []


def test_blocks_staged_reports(tmp_path: Path) -> None:
    _, forbidden_files = collect(
        tmp_path,
        staged={"reports/visualizations/dashboard.html"},
    )

    assert forbidden_files == [
        (
            "reports/visualizations/dashboard.html",
            "forbidden directory reports, staged",
        )
    ]


def test_blocks_staged_build_outputs(tmp_path: Path) -> None:
    _, forbidden_files = collect(
        tmp_path,
        staged={"live_chart/xref-LiveChartFeed.html"},
    )

    assert forbidden_files == [
        (
            "live_chart/xref-LiveChartFeed.html",
            "forbidden directory live_chart, staged",
        )
    ]


def test_blocks_secret_fallback_files(tmp_path: Path) -> None:
    _, forbidden_files = collect(
        tmp_path,
        staged={"api.env", "secrets/databento.env"},
    )

    assert forbidden_files == [
        ("api.env", "forbidden filename api.env, staged"),
        ("secrets/databento.env", "forbidden filename databento.env, staged"),
    ]


def test_allows_source_docs_and_manifest_metadata(tmp_path: Path) -> None:
    large_files, forbidden_files = collect(
        tmp_path,
        staged={
            "README.md",
            "scripts/check_git_hygiene.py",
            "manifests/feature_hypotheses/trial_statuses.jsonl",
            "manifests/data_inventory.csv",
        },
    )

    assert large_files == []
    assert forbidden_files == []
