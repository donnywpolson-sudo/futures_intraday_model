from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import consolidate_he_ke_le_dbn_parent_sources as tool


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return tool.sha256_file(path)


def _manifest(path: Path, *, rel_path: str, sha: str) -> None:
    path.with_name(path.name + ".manifest.json").write_text(
        json.dumps({"path": rel_path, "file_sha256": sha}, indent=2) + "\n",
        encoding="utf-8",
    )


def _audit_row(
    *,
    market: str = "KE",
    year: int = 2019,
    schema_key: str = "ohlcv_1m",
    parent_path: str = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst",
    parent_sha256: str = "abc",
    classification: str = "parquet_uses_parent",
) -> dict[str, object]:
    return {
        "market": market,
        "year": year,
        "schema_key": schema_key,
        "classification": classification,
        "parent_exists_and_differs_from_canonical": True,
        "parent_newer_than_canonical": True,
        "parent_manifest_source_summary": [
            {"path": parent_path, "file_sha256": parent_sha256}
        ],
    }


def _audit_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"summary": {"validation_status": "PASS"}, "rows": rows}


def _approval(
    *,
    parent_path: str = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst",
    parent_sha256: str,
    canonical_target_path: str = "data/dbn/ohlcv_1m/KE/2019/source.dbn.zst",
) -> tool.ApprovalRow:
    return tool.ApprovalRow(
        market="KE",
        year=2019,
        schema_key="ohlcv_1m",
        parent_path=parent_path,
        parent_sha256=parent_sha256,
        canonical_target_path=canonical_target_path,
        approved_action=tool.APPROVED_ACTION,
    )


def test_decision_packet_includes_ke_parent_lineage_years() -> None:
    rows = [
        _audit_row(year=year, parent_path=f"data/dbn/ohlcv_1m_parent/KE/{year}/source.dbn.zst")
        for year in [2019, 2021, 2023, 2024]
    ]

    packet = tool.build_decision_packet(_audit_payload(rows))

    assert packet["summary"]["default_parent_lineage_market_years"] == [
        "KE:2019",
        "KE:2021",
        "KE:2023",
        "KE:2024",
    ]
    assert packet["summary"]["recommendation_counts"] == {"promote_parent": 4}


def test_approval_hash_mismatch_stops_before_staging(tmp_path: Path) -> None:
    repo = tmp_path
    parent_rel = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst"
    actual_sha = _write(repo / parent_rel, b"parent")
    _manifest(repo / parent_rel, rel_path=parent_rel, sha=actual_sha)
    audit = _audit_payload([_audit_row(parent_path=parent_rel, parent_sha256="0" * 64)])
    approvals = [_approval(parent_path=parent_rel, parent_sha256="0" * 64)]

    with pytest.raises(ValueError, match="approved parent hash mismatch"):
        tool.validate_approvals_against_audit(approvals, audit, repo)


def test_stage_approved_rewrites_manifest_path_to_canonical(tmp_path: Path) -> None:
    repo = tmp_path
    parent_rel = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst"
    parent_sha = _write(repo / parent_rel, b"parent")
    _manifest(repo / parent_rel, rel_path=parent_rel, sha=parent_sha)
    approval = _approval(parent_path=parent_rel, parent_sha256=parent_sha)

    report = tool.stage_approved(
        repo,
        [approval],
        staging_root=Path("data/dbn/_promotion_staging"),
        timestamp="test",
        execute=True,
    )

    staged_manifest = (
        repo
        / report["staging_run_root"]
        / "data/dbn/ohlcv_1m/KE/2019/source.dbn.zst.manifest.json"
    )
    assert json.loads(staged_manifest.read_text(encoding="utf-8"))["path"] == (
        "data/dbn/ohlcv_1m/KE/2019/source.dbn.zst"
    )


def test_unapproved_rows_are_not_staged(tmp_path: Path) -> None:
    repo = tmp_path
    parent_rel = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst"
    parent_sha = _write(repo / parent_rel, b"parent")
    _manifest(repo / parent_rel, rel_path=parent_rel, sha=parent_sha)

    report = tool.stage_approved(
        repo,
        [],
        staging_root=Path("data/dbn/_promotion_staging"),
        timestamp="test",
        execute=True,
    )

    assert report["approved_row_count"] == 0
    assert not (repo / "data/dbn/_promotion_staging/test").exists()


def test_promote_archives_existing_canonical_before_overwrite(tmp_path: Path) -> None:
    repo = tmp_path
    parent_rel = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst"
    parent_sha = _write(repo / parent_rel, b"parent")
    _manifest(repo / parent_rel, rel_path=parent_rel, sha=parent_sha)
    approval = _approval(parent_path=parent_rel, parent_sha256=parent_sha)
    stage_report = tool.stage_approved(
        repo,
        [approval],
        staging_root=Path("data/dbn/_promotion_staging"),
        timestamp="test",
        execute=True,
    )
    canonical = repo / "data/dbn/ohlcv_1m/KE/2019/source.dbn.zst"
    canonical_sha = _write(canonical, b"canonical")
    _manifest(
        canonical,
        rel_path="data/dbn/ohlcv_1m/KE/2019/source.dbn.zst",
        sha=canonical_sha,
    )

    report = tool.promote_approved(
        repo,
        [approval],
        staging_run_root=Path(stage_report["staging_run_root"]),
        archive_root=Path("data/dbn/_archive_parent_consolidation"),
        timestamp="test",
        execute=True,
    )

    archive_path = repo / "data/dbn/_archive_parent_consolidation/test/data/dbn/ohlcv_1m/KE/2019/source.dbn.zst"
    assert archive_path.read_bytes() == b"canonical"
    assert canonical.read_bytes() == b"parent"
    assert report["actions"][0]["archive"] is not None


def test_parent_archive_blocks_missing_disposition(tmp_path: Path) -> None:
    repo = tmp_path
    _write(repo / "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst", b"parent")

    report = tool.archive_parent_roots(
        repo,
        {},
        archive_root=Path("data/dbn/_archive_parent_roots"),
        timestamp="test",
        execute=False,
    )

    assert report["status"] == "BLOCKED"
    assert report["missing_disposition_count"] == 1


def test_validate_raw_lineage_skips_empty_optional_stat_source_columns(tmp_path: Path) -> None:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    raw = tmp_path / "data/raw/KE/2019.parquet"
    raw.parent.mkdir(parents=True)
    ohlcv = "data/dbn/ohlcv_1m/KE/2019/source.dbn.zst"
    status = "data/dbn/status/KE/2019/source.dbn.zst"
    statistics = "data/dbn/statistics/KE/2019/source.dbn.zst"
    pd.DataFrame(
        [
            {
                "source_file": ohlcv,
                "source_sha256": "a" * 64,
                "status_source_file": status,
                "status_source_sha256": "b" * 64,
                "stat_opening_price_source_file": statistics,
                "stat_opening_price_source_sha256": "c" * 64,
                "stat_close_price_missing": True,
                "stat_close_price_source_file": None,
                "stat_close_price_source_sha256": None,
            }
        ]
    ).to_parquet(raw)

    approvals = [
        tool.ApprovalRow("KE", 2019, "ohlcv_1m", "parent", "a" * 64, ohlcv, tool.APPROVED_ACTION),
        tool.ApprovalRow("KE", 2019, "status", "parent", "b" * 64, status, tool.APPROVED_ACTION),
        tool.ApprovalRow("KE", 2019, "statistics", "parent", "c" * 64, statistics, tool.APPROVED_ACTION),
    ]

    assert tool.validate_raw_lineage(tmp_path, approvals) == []


def test_stage_dry_run_lists_copy_and_raw_regeneration_without_touching_files(tmp_path: Path) -> None:
    repo = tmp_path
    parent_rel = "data/dbn/ohlcv_1m_parent/KE/2019/source.dbn.zst"
    parent_sha = _write(repo / parent_rel, b"parent")
    _manifest(repo / parent_rel, rel_path=parent_rel, sha=parent_sha)
    approval = _approval(parent_path=parent_rel, parent_sha256=parent_sha)

    report = tool.stage_approved(
        repo,
        [approval],
        staging_root=Path("data/dbn/_promotion_staging"),
        timestamp="test",
        execute=False,
    )

    assert report["actions"][0]["action"] == "copy_parent_to_staging"
    assert "download_databento_raw --mode convert-parquet" in report["raw_regeneration_commands"][0]["command"]
    assert not (repo / "data/dbn/_promotion_staging/test").exists()
