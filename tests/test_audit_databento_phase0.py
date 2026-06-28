from __future__ import annotations

from pathlib import Path

from scripts.audit_databento_phase0 import classify_folder, parse_dbn_market_year_schema


def test_folder_classification_identifies_canonical_and_derived() -> None:
    assert classify_folder(Path("data/dbn"))[0] == "canonical_raw_source"
    assert classify_folder(Path("data/raw"))[0] == "current_derived"
    assert classify_folder(Path("data/causally_gated_normalized_pre_replace_TEST_FIXTURE"))[0] == "quarantine_candidate"
    assert classify_folder(Path("data/example_sr_parent_candidate/nested"))[0] == "quarantine_candidate"
    assert classify_folder(Path("data/mystery"))[0] == "unsafe_unknown"


def test_market_year_schema_parsing_for_dbn_path() -> None:
    path = Path("data/dbn/ohlcv_1m/ES/2026/2026-01-01_2026-01-02.dbn.zst")

    parsed = parse_dbn_market_year_schema(path)

    assert parsed == {"schema": "ohlcv-1m", "market": "ES", "year": "2026"}


def test_market_year_schema_parsing_handles_status_parent_shape() -> None:
    path = Path("data/dbn/status_parent/status/KE/2023/2023-01-01_2024-01-01.dbn.zst")

    parsed = parse_dbn_market_year_schema(path)

    assert parsed["market"] == "KE"
    assert parsed["year"] == "2023"
