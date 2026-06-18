from __future__ import annotations

from pathlib import Path

import yaml

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


def _touch_expected_archive(path: str) -> None:
    archive = Path(path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"dbn")
    archive.with_name(f"{archive.name}.manifest.json").write_text("{}", encoding="utf-8")


def test_dbn_archive_coverage_fails_closed_for_missing_strict_tier3_v2_roots(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["SR1", "TN", "ZL", "ZM", "KE"], [2024])

    report = build_report(
        config_path=config,
        profile="tier_3",
        dbn_root=tmp_path / "data" / "dbn" / "ohlcv_1m",
    )

    assert report["status"] == "FAIL"
    assert report["expected_archive_count"] == 10
    assert report["missing_archive_count"] == 10
    assert report["missing_archives_by_market"] == {
        "KE": 2,
        "SR1": 2,
        "TN": 2,
        "ZL": 2,
        "ZM": 2,
    }


def test_dbn_archive_coverage_passes_with_ohlcv_definition_and_manifests(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES", "SR1"], [2018])
    dbn_root = tmp_path / "data" / "dbn" / "ohlcv_1m"
    seed = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)
    for row in seed["missing_archives"]:
        _touch_expected_archive(str(row["path"]))

    report = build_report(config_path=config, profile="tier_3_research", dbn_root=dbn_root)

    assert report["status"] == "PASS"
    assert report["schemas"] == list(DEFAULT_SCHEMAS)
    assert report["missing_archive_count"] == 0
    assert report["missing_manifest_count"] == 0


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
    assert strict["missing_manifest_count"] == 2
    assert archive_only["status"] == "PASS"
