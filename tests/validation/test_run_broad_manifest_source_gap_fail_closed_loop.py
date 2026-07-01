from __future__ import annotations

from pathlib import Path

from scripts.validation.run_broad_manifest_source_gap_fail_closed_loop import (
    _exclude_pair_payload,
    _same_source_gap_pattern,
)


def test_same_source_gap_pattern_requires_matching_timestamp_sets() -> None:
    assert _same_source_gap_pattern(
        {
            "source_vs_raw_call": "raw_timestamp_set_matches_ohlcv_dbn_source_gaps",
            "timestamp_sets_match": True,
            "dbn_timestamps_missing_from_raw_count": 0,
            "raw_timestamps_missing_from_dbn_count": 0,
        }
    )
    assert not _same_source_gap_pattern(
        {
            "source_vs_raw_call": "conversion_or_raw_write_dropped_dbn_timestamps_possible",
            "timestamp_sets_match": False,
            "dbn_timestamps_missing_from_raw_count": 1,
            "raw_timestamps_missing_from_dbn_count": 0,
        }
    )


def test_exclude_pair_payload_removes_exact_row_and_preserves_safety_flags() -> None:
    payload = {
        "summary": {
            "approval_token": "old",
            "build_approved": True,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
        },
        "market_years": [
            {"market": "6B", "year": 2015},
            {"market": "6B", "year": 2016},
        ],
        "excluded_fail_closed_pairs": ["6A:2010"],
    }

    result = _exclude_pair_payload(
        include_payload=payload,
        pair="6B:2016",
        diagnosis_json=Path("reports/diag.json"),
        source_include=Path("reports/include.json"),
    )

    assert result["market_years"] == [{"market": "6B", "year": 2015}]
    assert result["excluded_fail_closed_pairs"] == ["6A:2010", "6B:2016"]
    assert result["summary"]["approved_ready_row_count"] == 1
    assert result["summary"]["broader_modeling_approved"] is False
    assert result["summary"]["config_promotion_approved"] is False
    assert result["summary"]["research_use_allowed"] is False
