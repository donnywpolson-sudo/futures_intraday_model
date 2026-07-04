from __future__ import annotations

import json
from pathlib import Path

from scripts.phase1A_download.download_databento_raw import DownloadTask, build_raw_file_manifest
from scripts.validation import build_local_trade_optional_archive_inventory as inventory


def _archive_path(tmp_path: Path, schema: str, market: str = "ES") -> Path:
    return (
        tmp_path
        / "data"
        / "dbn"
        / schema
        / market
        / "2026"
        / "2026-01-01_2026-06-13.dbn.zst"
    )


def _write_archive(
    tmp_path: Path,
    schema: str,
    market: str = "ES",
    *,
    manifest_start: str = "2026-01-01",
    manifest_end: str = "2026-06-13",
    manifest_schema: str | None = None,
) -> Path:
    archive_path = _archive_path(tmp_path, schema, market)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(f"{market} {schema} archive".encode("utf-8"))
    task = DownloadTask(
        dataset="GLBX.MDP3",
        product=market,
        year=2026,
        start=manifest_start,
        end=manifest_end,
        symbol=f"{market}.v.0",
        output_path=archive_path.as_posix(),
        schema=manifest_schema or schema,
        raw_format="dbn-zstd",
    )
    manifest = build_raw_file_manifest(task, archive_path, job_id="test", request_status="ok")
    archive_path.with_name(f"{archive_path.name}.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    return archive_path


def _write_complete_market(tmp_path: Path, market: str = "ES") -> None:
    for schema in inventory.DEFAULT_SCHEMAS:
        _write_archive(tmp_path, schema, market)


def _build(tmp_path: Path, *, markets: list[str] | None = None) -> dict[str, object]:
    return inventory.build_report(
        repo_root=tmp_path,
        dbn_root=tmp_path / "data" / "dbn",
        markets=markets,
        expected_market_count=len(markets) if markets is not None else None,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
    )


def test_ready_when_selected_markets_have_valid_status_and_statistics(tmp_path: Path) -> None:
    _write_complete_market(tmp_path, "ES")
    _write_complete_market(tmp_path, "CL")

    report = _build(tmp_path, markets=["CL", "ES"])

    assert report["summary"]["status"] == inventory.STATUS_READY
    assert report["summary"]["market_count"] == 2
    assert report["summary"]["ready_market_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["provider_download_approved"] is False


def test_discovers_markets_from_schema_directories(tmp_path: Path) -> None:
    _write_complete_market(tmp_path, "ES")

    report = _build(tmp_path)

    assert report["summary"]["status"] == inventory.STATUS_READY
    assert report["markets"] == ["ES"]


def test_missing_schema_archive_fails_closed(tmp_path: Path) -> None:
    _write_archive(tmp_path, "statistics", "ES")

    report = _build(tmp_path, markets=["ES"])

    assert report["summary"]["status"] == inventory.STATUS_NO_GO
    assert report["summary"]["invalid_archive_count"] == 1
    assert report["invalid_markets"] == ["ES"]


def test_wrong_manifest_window_fails_closed(tmp_path: Path) -> None:
    _write_archive(tmp_path, "statistics", "ES", manifest_end="2026-12-31")
    _write_archive(tmp_path, "status", "ES")

    report = _build(tmp_path, markets=["ES"])

    assert report["summary"]["status"] == inventory.STATUS_NO_GO
    observed = next(check for check in report["checks"] if check["name"] == "optional_archive_manifests_valid")[
        "observed"
    ]
    assert any("manifest end mismatch" in failure for item in observed for failure in item["failures"])


def test_wrong_manifest_schema_fails_closed(tmp_path: Path) -> None:
    _write_archive(tmp_path, "statistics", "ES", manifest_schema="status")
    _write_archive(tmp_path, "status", "ES")

    report = _build(tmp_path, markets=["ES"])

    observed = next(check for check in report["checks"] if check["name"] == "optional_archive_manifests_valid")[
        "observed"
    ]
    assert report["summary"]["status"] == inventory.STATUS_NO_GO
    assert any("manifest schema mismatch" in failure for item in observed for failure in item["failures"])


def test_expected_market_count_mismatch_fails_closed(tmp_path: Path) -> None:
    _write_complete_market(tmp_path, "ES")

    report = inventory.build_report(
        repo_root=tmp_path,
        dbn_root=tmp_path / "data" / "dbn",
        expected_market_count=2,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=[],
    )

    assert report["summary"]["status"] == inventory.STATUS_NO_GO
    assert any(
        check["name"] == "expected_market_count_met"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_path_fails_closed(tmp_path: Path) -> None:
    _write_complete_market(tmp_path, "ES")

    report = inventory.build_report(
        repo_root=tmp_path,
        dbn_root=tmp_path / "data" / "dbn",
        markets=["ES"],
        expected_market_count=1,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=["reports/generated.json"],
    )

    assert report["summary"]["status"] == inventory.STATUS_NO_GO
    assert any(
        check["name"] == "staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
