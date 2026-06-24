from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.phase1A_download.download_databento_raw import (
    CME_DATASET,
    DownloadTask,
    build_raw_file_manifest,
    symbol_for_product,
)
from scripts.validation.check_dbn_archive_coverage import (
    DEFAULT_SCHEMAS,
    build_report,
)


def _write_config(path: Path, markets: list[str], years: list[int]) -> Path:
    payload = {
        "profiles": {
            "tier_3_research": {
                "markets": markets,
                "years": years,
            }
        },
        "aliases": {"tier_3": "tier_3_research"},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _touch_expected_archive(row: dict[str, object]) -> None:
    archive = Path(str(row["path"]))
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"dbn")
    schema = str(row["schema"])
    market = str(row["market"])
    stype_in = "parent" if schema == "definition" else "continuous"
    task = DownloadTask(
        dataset=CME_DATASET,
        product=market,
        year=int(row["year"]),
        start=str(row["start"]),
        end=str(row["end"]),
        symbol=symbol_for_product(market, stype_in),
        output_path=archive.as_posix(),
        schema=schema,
        stype_in=stype_in,
        stype_out="instrument_id",
        chunk="year",
        raw_format="dbn-zstd",
    )
    archive.with_name(f"{archive.name}.manifest.json").write_text(
        json.dumps(build_raw_file_manifest(task, archive, job_id="job-test", request_status="ok"), indent=2),
        encoding="utf-8",
    )


def test_dbn_archive_coverage_fails_closed_for_missing_strict_tier3_v2_roots(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["SR1", "TN", "ZL", "ZM", "KE"], [2024])

    report = build_report(
        config_path=config,
        profile="tier_3",
        dbn_root=tmp_path / "data" / "dbn" / "ohlcv_1m",
    )

    assert report["status"] == "FAIL"
    assert report["expected_archive_count"] == 20
    assert report["missing_archive_count"] == 20
    assert report["missing_archives_by_market"] == {
        "KE": 4,
        "SR1": 4,
        "TN": 4,
        "ZL": 4,
        "ZM": 4,
    }


def test_dbn_archive_coverage_passes_with_required_phase1a_schemas_and_manifests(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES", "SR1"], [2018])
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    seed = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)
    for row in seed["missing_archives"]:
        _touch_expected_archive(row)

    report = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)

    assert report["status"] == "PASS"
    assert report["schemas"] == list(DEFAULT_SCHEMAS)
    assert report["missing_archive_count"] == 0
    assert report["missing_manifest_count"] == 0
    assert report["invalid_manifest_count"] == 0
    assert report["extra_market_dir_count"] == 0


def test_dbn_archive_coverage_accepts_parent_dbn_root(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2018])
    dbn_root = tmp_path / "data" / "dbn"
    seed = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)
    for row in seed["missing_archives"]:
        _touch_expected_archive(row)

    report = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)

    assert report["status"] == "PASS"
    assert report["effective_dbn_root"].endswith("data/dbn/ohlcv_1m")
    assert report["missing_archive_count"] == 0


def test_dbn_archive_coverage_can_ignore_manifests_for_archive_only_probe(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    seed = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)
    for row in seed["missing_archives"]:
        archive = Path(str(row["path"]))
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"dbn")

    strict = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)
    archive_only = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        require_manifests=False,
    )

    assert strict["status"] == "FAIL"
    assert strict["missing_archive_count"] == 0
    assert strict["missing_manifest_count"] == 4
    assert archive_only["status"] == "PASS"


def test_dbn_archive_coverage_rejects_optional_required_phase1a_schemas(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"

    with pytest.raises(ValueError, match="Phase 1A downstream readiness schemas cannot be optional: status"):
        build_report(
            config_path=config,
            profile="tier_3_research",
            dbn_root=dbn_root,
            optional_schemas=("status",),
        )


def test_dbn_archive_coverage_still_fails_missing_required_schema(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    seed = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("ohlcv-1m", "definition", "status"),
    )
    for row in seed["missing_archives"]:
        if row["schema"] == "ohlcv-1m":
            _touch_expected_archive(row)

    report = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("ohlcv-1m", "definition", "status"),
    )

    assert report["status"] == "FAIL"
    assert report["missing_archive_count"] == 2
    assert report["missing_archives_by_schema"] == {"definition": 1, "status": 1}


def test_dbn_archive_coverage_uses_partial_current_year_end_date(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2026])
    dbn_root = tmp_path / "data" / "dbn"
    seed = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("ohlcv-1m", "definition"),
        end_date="2026-06-13",
    )

    assert seed["expected_archive_count"] == 2
    assert all("2026-01-01_2026-06-13.dbn.zst" in row["path"] for row in seed["missing_archives"])

    for row in seed["missing_archives"]:
        _touch_expected_archive(row)
    report = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("ohlcv-1m", "definition"),
        end_date="2026-06-13",
    )

    assert report["status"] == "PASS"
    assert report["audit_end"] == "2026-06-13"


def test_dbn_archive_coverage_checks_supported_schema_aliases_and_extra_dirs(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    seed = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("tick-all",),
    )

    assert seed["schemas"] == ["mbp-1", "trades"]
    assert seed["expected_archive_count"] == 2


def test_dbn_archive_coverage_flags_invalid_manifests_and_extra_market_dirs(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    seed = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("trades",),
    )
    row = seed["missing_archives"][0]
    _touch_expected_archive(row)
    manifest_path = Path(str(row["manifest_path"]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "mbp-1"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (tmp_path / "data" / "dbn" / "trades" / "6N").mkdir(parents=True)

    report = build_report(
        config_path=config,
        profile="tier_3_research",
        dbn_root=dbn_root,
        schemas=("trades",),
    )

    assert report["status"] == "FAIL"
    assert report["missing_archive_count"] == 0
    assert report["invalid_manifest_count"] == 1
    assert report["extra_market_dirs_by_schema"] == {"trades": ["6N"]}
