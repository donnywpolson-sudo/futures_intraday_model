from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pandas as pd
import yaml

from scripts.phase1A_download.download_databento_raw import (
    CME_DATASET,
    DownloadTask,
    build_raw_file_manifest,
    file_sha256,
    schema_path_name,
    symbol_for_product,
)
from scripts.validation.audit_raw_dbn_alignment import build_report
from scripts.validation.triage_raw_dbn_alignment import (
    build_definition_path_report,
    build_definition_drilldown,
    build_definition_root_cause,
    build_missing_raw_path_report,
    build_promotion_manifest,
    build_source_path_report,
    compare_candidate_to_raw,
    preferred_non_overlapping_paths,
)


class FakeStore:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def to_df(self, **_: object) -> pd.DataFrame:
        return self.df.copy()


def _write_config(path: Path, markets: list[str], years: list[int]) -> Path:
    payload = {
        "profiles": {"tier_3_research": {"markets": markets, "years": years}},
        "aliases": {"tier_3": "tier_3_research"},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _dbn_path(root: Path, schema: str, market: str, year: int) -> Path:
    return root / schema_path_name(schema) / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst"


def _write_dbn_with_manifest(root: Path, schema: str, market: str = "ES", year: int = 2024) -> Path:
    path = _dbn_path(root, schema, market, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{schema}-{market}-{year}".encode("utf-8"))
    stype_in = "parent" if schema == "definition" else "continuous"
    task = DownloadTask(
        dataset=CME_DATASET,
        product=market,
        year=year,
        start=f"{year}-01-01",
        end=f"{year + 1}-01-01",
        symbol=symbol_for_product(market, stype_in),
        output_path=path.as_posix(),
        schema=schema,
        stype_in=stype_in,
        stype_out="instrument_id",
        chunk="year",
        raw_format="dbn-zstd",
    )
    path.with_name(f"{path.name}.manifest.json").write_text(
        json.dumps(build_raw_file_manifest(task, path, job_id="job-test", request_status="ok"), indent=2),
        encoding="utf-8",
    )
    return path


def _definition_frame(
    *,
    raw_symbol: str = "ESH4",
    tick_size: float = 0.25,
    multiplier: float = 50.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "instrument_id": [100],
            "raw_symbol": [raw_symbol],
            "min_price_increment": [tick_size],
            "contract_multiplier": [multiplier],
        }
    )


def _install_fake_databento(monkeypatch, mapping: dict[Path, pd.DataFrame]) -> None:
    class FakeDBNStore:
        @classmethod
        def from_file(cls, path: Path) -> FakeStore:
            return FakeStore(mapping[path])

    monkeypatch.setitem(sys.modules, "databento", types.SimpleNamespace(DBNStore=FakeDBNStore))


def _write_raw(
    raw_root: Path,
    ohlcv_path: Path,
    *,
    market: str = "ES",
    year: int = 2024,
    raw_symbol: str = "ESH4",
    tick_size: float = 0.25,
    source_sha256: str | None = None,
    drop_columns: list[str] | None = None,
) -> Path:
    path = raw_root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts_event": pd.Timestamp(f"{year}-01-02T15:00:00Z"),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": 100,
        "symbol": raw_symbol,
        "data_quality_status": "available",
        "data_quality_degraded": False,
        "market": market,
        "year": year,
        "raw_symbol": raw_symbol,
        "tick_size": tick_size,
        "contract_multiplier_or_point_value": 50.0,
        "source_file": ohlcv_path.as_posix(),
        "source_sha256": source_sha256 or file_sha256(ohlcv_path),
    }
    for column in drop_columns or []:
        row.pop(column, None)
    pd.DataFrame([row]).to_parquet(path, index=False)
    return path


def test_raw_dbn_alignment_passes_clean_market_year(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv)
    _install_fake_databento(monkeypatch, {definition: _definition_frame()})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "PASS"
    assert report["raw_schema_failure_count"] == 0
    assert report["source_hash_mismatch_count"] == 0
    assert report["definition_join_mismatch_count"] == 0


def test_raw_dbn_alignment_reports_dbn_only_market_year_as_phase1b_gap(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _install_fake_databento(monkeypatch, {definition: _definition_frame()})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=tmp_path / "data" / "raw")

    assert report["status"] == "FAIL"
    assert report["missing_raw_count"] == 1
    assert report["needs_phase1b_conversion"] == [{"market": "ES", "year": 2024, "status": "needs_phase1b_conversion"}]
    assert ohlcv.exists()


def test_raw_dbn_alignment_reports_missing_definition_dbn(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    _write_raw(raw_root, ohlcv)

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "FAIL"
    assert report["missing_definition_dbn_count"] == 1
    assert report["raw_only_count"] == 1


def test_raw_dbn_alignment_reports_raw_schema_column_failure(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, drop_columns=["tick_size"])
    _install_fake_databento(monkeypatch, {definition: _definition_frame()})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "FAIL"
    assert report["raw_schema_failure_count"] == 1
    assert "tick_size" in report["raw_schema_failures"][0]["failures"][0]


def test_raw_dbn_alignment_reports_source_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, source_sha256="bad-hash")
    _install_fake_databento(monkeypatch, {definition: _definition_frame()})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "FAIL"
    assert report["source_hash_mismatch_count"] == 1


def test_raw_dbn_alignment_skip_definition_join_still_reports_hash_failure(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, source_sha256="bad-hash")

    report = build_report(
        config_path=config,
        profile="tier_3",
        dbn_root=dbn_root,
        raw_root=raw_root,
        skip_definition_join=True,
    )

    assert report["audit_completeness"] == "partial"
    assert report["definition_join_skipped"] is True
    assert report["definition_join_status"] == "skipped"
    assert report["definition_join_checked_market_year_count"] == 0
    assert report["source_hash_mismatch_count"] == 1
    assert report["definition_join_mismatch_count"] == 0


def test_raw_dbn_alignment_reports_raw_only_extra_market(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    es_ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES")
    es_definition = _write_dbn_with_manifest(dbn_root, "definition", "ES")
    nq_ohlcv_placeholder = raw_root / "NQ" / "2024.dbn.zst"
    nq_ohlcv_placeholder.parent.mkdir(parents=True, exist_ok=True)
    nq_ohlcv_placeholder.write_bytes(b"not-canonical")
    _write_raw(raw_root, es_ohlcv, market="ES", raw_symbol="ESH4")
    _write_raw(raw_root, nq_ohlcv_placeholder, market="NQ", raw_symbol="NQH4")
    _install_fake_databento(monkeypatch, {es_definition: _definition_frame()})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "FAIL"
    assert report["raw_only_market_years"] == [
        {"market": "NQ", "year": 2024, "path": (raw_root / "NQ" / "2024.parquet").as_posix()}
    ]


def test_raw_dbn_alignment_exempts_pre_availability_year(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["SR1"], [2017])

    report = build_report(
        config_path=config,
        profile="tier_3",
        dbn_root=tmp_path / "data" / "dbn",
        raw_root=tmp_path / "data" / "raw",
    )

    assert report["status"] == "PASS"
    assert report["expected_market_year_count"] == 0
    assert report["pre_availability_exemption_count"] == 1


def test_raw_dbn_alignment_reports_definition_join_mismatch(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.50)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})

    report = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    assert report["status"] == "FAIL"
    assert report["definition_join_mismatch_count"] == 1
    assert report["definition_join_mismatches"][0]["mismatch_counts"] == {"tick_size": 1}


def test_raw_alignment_source_path_report_selects_mismatch_year_only(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    selected = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES", 2026)
    _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "NQ", 2025)
    alignment = {
        "source_hash_mismatches": [
            {"market": "ES", "year": 2026},
            {"market": "NQ", "year": 2025},
        ]
    }

    report = build_source_path_report(alignment_report=alignment, dbn_root=dbn_root, year=2026)

    assert report["market_year_count"] == 1
    assert report["paths"] == [selected.as_posix()]


def test_raw_alignment_candidate_compare_detects_identity_difference(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES", 2026)
    _write_raw(raw_root, ohlcv, year=2026)
    _write_raw(candidate_root, ohlcv, year=2026)
    candidate_path = candidate_root / "ES" / "2026.parquet"
    candidate = pd.read_parquet(candidate_path)
    candidate.loc[0, "close"] = 101.5
    candidate.to_parquet(candidate_path, index=False)

    report = compare_candidate_to_raw(
        keys=[("ES", 2026)],
        base_root=raw_root,
        candidate_root=candidate_root,
        dbn_root=dbn_root,
    )

    assert report["status"] == "FAIL"
    assert report["rows"][0]["identity_difference_count"] == 1
    assert report["rows"][0]["candidate_hashes_match_local_dbn"] is True


def test_raw_alignment_definition_drilldown_groups_instruments(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path / "alpha_tiered.yaml", ["ES"], [2024])
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.50)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})
    alignment = build_report(config_path=config, profile="tier_3", dbn_root=dbn_root, raw_root=raw_root)

    drilldown = build_definition_drilldown(
        alignment_report=alignment,
        dbn_root=dbn_root,
        raw_root=raw_root,
    )

    assert drilldown["market_year_count"] == 1
    assert drilldown["classifications"] == {"raw_metadata_stale_against_current_definition_dbn": 1}
    field = drilldown["rows"][0]["fields"][0]
    assert field["field"] == "tick_size"
    assert field["affected_instrument_count"] == 1
    assert field["top_instruments"][0]["instrument_id"] == "100"


def test_raw_alignment_missing_path_report_excludes_existing_raw(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    missing = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES", 2024)
    existing = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "NQ", 2024)
    _write_raw(raw_root, existing, market="NQ", raw_symbol="NQH4")
    alignment = {
        "needs_phase1b_conversion": [
            {"market": "ES", "year": 2024},
            {"market": "NQ", "year": 2024},
        ]
    }

    report = build_missing_raw_path_report(
        alignment_report=alignment,
        dbn_root=dbn_root,
        raw_root=raw_root,
    )

    assert report["market_year_count"] == 1
    assert report["paths"] == [missing.as_posix()]


def test_raw_alignment_path_selection_excludes_contained_overlap(tmp_path: Path) -> None:
    full = tmp_path / "2026-01-01_2026-06-13.dbn.zst"
    contained = tmp_path / "2026-06-12_2026-06-13.dbn.zst"
    adjacent = tmp_path / "2026-06-13_2026-06-14.dbn.zst"
    for path in [full, contained, adjacent]:
        path.write_bytes(b"dbn")

    selected = preferred_non_overlapping_paths([contained, adjacent, full])

    assert selected == [full, adjacent]


def test_raw_alignment_definition_path_report_uses_overlap_filtered_paths(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    full = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES", 2026)
    contained = dbn_root / "ohlcv_1m" / "ES" / "2026" / "2026-06-12_2026-06-13.dbn.zst"
    contained.write_bytes(b"contained")
    alignment = {"definition_join_mismatches": [{"market": "ES", "year": 2026}]}

    report = build_definition_path_report(alignment_report=alignment, dbn_root=dbn_root)

    assert report["paths"] == [full.as_posix()]


def test_raw_alignment_candidate_compare_classifies_metadata_only(tmp_path: Path) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m", "ES", 2024)
    _write_raw(raw_root, ohlcv, tick_size=0.25)
    _write_raw(candidate_root, ohlcv, tick_size=0.50)

    report = compare_candidate_to_raw(
        keys=[("ES", 2024)],
        base_root=raw_root,
        candidate_root=candidate_root,
        dbn_root=dbn_root,
    )

    assert report["rows"][0]["change_type"] == "metadata_only"
    assert report["rows"][0]["metadata_difference_counts"] == {"tick_size": 1}
    assert report["rows"][0]["identity_difference_count"] == 0


def test_raw_alignment_promotion_manifest_dedupes_candidate_groups(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    candidate_2026_root = tmp_path / "data" / "candidate_2026"
    definition_root = tmp_path / "data" / "candidate_definition"
    missing_root = tmp_path / "data" / "candidate_missing"
    dbn_placeholder = tmp_path / "dbn.zst"
    dbn_placeholder.write_bytes(b"dbn")
    _write_raw(raw_root, dbn_placeholder, market="ES", year=2026)
    _write_raw(candidate_2026_root, dbn_placeholder, market="ES", year=2026)
    _write_raw(definition_root, dbn_placeholder, market="ES", year=2026, tick_size=0.50)
    _write_raw(missing_root, dbn_placeholder, market="KE", year=2024)
    alignment = {
        "source_hash_mismatches": [{"market": "ES", "year": 2026}],
        "definition_join_mismatches": [{"market": "ES", "year": 2026}],
        "needs_phase1b_conversion": [{"market": "KE", "year": 2024}],
    }

    manifest = build_promotion_manifest(
        alignment_report=alignment,
        raw_root=raw_root,
        candidate_2026_root=candidate_2026_root,
        definition_candidate_root=definition_root,
        missing_candidate_root=missing_root,
    )

    assert manifest["market_year_count"] == 2
    assert manifest["ready_count"] == 2
    es_row = next(row for row in manifest["rows"] if row["market"] == "ES")
    assert es_row["action"] == "replace_with_definition_fix_candidate"
    assert es_row["groups"] == ["definition_mismatch", "source_hash_2026"]
    ke_row = next(row for row in manifest["rows"] if row["market"] == "KE")
    assert ke_row["action"] == "add_missing_raw"


def test_definition_root_cause_classifies_candidate_fix_and_samples_values(tmp_path: Path, monkeypatch) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.50)
    _write_raw(candidate_root, ohlcv, tick_size=0.25)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})

    report = build_definition_root_cause(
        alignment_report={"definition_join_mismatches": [{"market": "ES", "year": 2024}]},
        candidate_compare_report={"rows": [{"market": "ES", "year": 2024, "change_type": "metadata_only"}]},
        dbn_root=dbn_root,
        raw_root=raw_root,
        candidate_root=candidate_root,
    )

    assert report["classifications"] == {"candidate_fixes_stale_raw_metadata": 1}
    row = report["rows"][0]
    assert row["canonical_mismatch_counts"] == {"tick_size": 1}
    assert row["candidate_mismatch_counts"] == {}
    sample = row["sample_rows"][0]
    assert sample["field"] == "tick_size"
    assert sample["canonical_value"] == "0.5"
    assert sample["candidate_value"] == "0.25"
    assert sample["definition_value"] == "0.25"


def test_definition_root_cause_classifies_audit_rule_false_positive(tmp_path: Path, monkeypatch) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.25)
    _write_raw(candidate_root, ohlcv, tick_size=0.25)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})

    report = build_definition_root_cause(
        alignment_report={"definition_join_mismatches": [{"market": "ES", "year": 2024}]},
        candidate_compare_report={"rows": [{"market": "ES", "year": 2024, "change_type": "unchanged"}]},
        dbn_root=dbn_root,
        raw_root=raw_root,
        candidate_root=candidate_root,
    )

    assert report["classifications"] == {"audit_rule_index_alignment_false_positive": 1}
    assert report["rows"][0]["canonical_mismatch_counts"] == {}
    assert report["rows"][0]["candidate_mismatch_counts"] == {}


def test_definition_root_cause_classifies_unchanged_mismatch(tmp_path: Path, monkeypatch) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.50)
    _write_raw(candidate_root, ohlcv, tick_size=0.50)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})

    report = build_definition_root_cause(
        alignment_report={"definition_join_mismatches": [{"market": "ES", "year": 2024}]},
        candidate_compare_report={"rows": [{"market": "ES", "year": 2024, "change_type": "unchanged"}]},
        dbn_root=dbn_root,
        raw_root=raw_root,
        candidate_root=candidate_root,
    )

    assert report["classifications"] == {"candidate_unchanged_definition_mismatch": 1}
    assert report["representative_samples"]["unchanged"]["market"] == "ES"


def test_definition_root_cause_classifies_tail_addition_without_metadata_fix(tmp_path: Path, monkeypatch) -> None:
    dbn_root = tmp_path / "data" / "dbn"
    raw_root = tmp_path / "data" / "raw"
    candidate_root = tmp_path / "data" / "candidate"
    ohlcv = _write_dbn_with_manifest(dbn_root, "ohlcv-1m")
    definition = _write_dbn_with_manifest(dbn_root, "definition")
    _write_raw(raw_root, ohlcv, tick_size=0.50)
    candidate_path = _write_raw(candidate_root, ohlcv, tick_size=0.50)
    candidate = pd.read_parquet(candidate_path)
    extra = candidate.iloc[0].copy()
    extra["ts_event"] = pd.Timestamp("2024-01-02T15:01:00Z")
    pd.concat([candidate, pd.DataFrame([extra])], ignore_index=True).to_parquet(candidate_path, index=False)
    _install_fake_databento(monkeypatch, {definition: _definition_frame(tick_size=0.25)})

    report = build_definition_root_cause(
        alignment_report={"definition_join_mismatches": [{"market": "ES", "year": 2024}]},
        candidate_compare_report={"rows": [{"market": "ES", "year": 2024, "change_type": "tail_addition"}]},
        dbn_root=dbn_root,
        raw_root=raw_root,
        candidate_root=candidate_root,
    )

    assert report["classifications"] == {"tail_addition_no_metadata_fix": 1}
    row = report["rows"][0]
    assert row["canonical_rows"] == 1
    assert row["candidate_rows"] == 2
    assert row["candidate_overlap_mismatch_counts"] == {"tick_size": 1}
    assert report["representative_samples"]["tail_addition"]["market"] == "ES"
