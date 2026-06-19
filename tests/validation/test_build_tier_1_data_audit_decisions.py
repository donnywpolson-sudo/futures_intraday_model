from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from scripts.validation.build_tier_1_data_audit_decisions import build_report, main


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(
    tmp_path: Path,
    *,
    provenance_paths: list[Path],
    local_trades_paths: list[Path] | None = None,
) -> Namespace:
    return Namespace(
        decision_table_json=str(tmp_path / "reports" / "decisions.json"),
        provenance_json=[str(path) for path in provenance_paths],
        local_trades_gap_json=[str(path) for path in local_trades_paths or []],
        json_out=str(tmp_path / "reports" / "decisions_out.json"),
        md_out=str(tmp_path / "reports" / "decisions_out.md"),
    )


def _write_base_decisions(path: Path) -> None:
    _write_json(
        path,
        {
            "rows": [
                {
                    "market": "ES",
                    "year": 2023,
                    "missing_minute_status": "PASS",
                    "provenance_status": "PASS",
                    "provenance_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
                    "synthetic_rows": 274,
                    "active_session_synthetic_rows": 6,
                    "largest_gap_size_minutes": 3,
                    "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
                    "reason": "preserve me",
                    "failures": [],
                }
            ]
        },
    )


def _base_decision(market: str, year: int) -> dict[str, object]:
    return {
        "market": market,
        "year": year,
        "missing_minute_status": "PASS",
        "provenance_status": "PASS",
        "provenance_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
        "synthetic_rows": 274,
        "active_session_synthetic_rows": 6,
        "largest_gap_size_minutes": 3,
        "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
        "reason": "preserve me",
        "failures": [],
    }


def _write_local_trades_gap_report(
    path: Path,
    *,
    market: str = "ES",
    years: list[int] | None = None,
    status: str = "PASS",
    start: str = "2025-06-18T00:00:00Z",
    end: str = "2026-06-13T00:00:00Z",
    missing: int = 4,
    verified: int = 4,
    failed: int = 0,
    unverified: int = 0,
    archives: int = 1,
) -> None:
    _write_json(
        path,
        {
            "status": status,
            "window": {"start": start, "end": end},
            "market_years": [
                {
                    "market": market,
                    "year": year,
                    "status": status,
                    "summary": {
                        "missing_minute_count": missing,
                        "verified_empty_minutes": verified,
                        "failed_minutes": failed,
                        "unverified_minutes": unverified,
                        "trade_rows_scanned": 100,
                        "archives_read": archives,
                    },
                }
                for year in (years or [2025, 2026])
            ],
        },
    )


def test_adds_roll_symbol_instrument_counts_from_provenance(tmp_path: Path) -> None:
    _write_base_decisions(tmp_path / "reports" / "decisions.json")
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(
        provenance,
        {
            "entries": [
                {
                    "market": "ES",
                    "year": 2023,
                    "continuity": {
                        "roll_window_synthetic_rows": 1,
                        "symbol_change_synthetic_rows": 0,
                        "instrument_id_change_synthetic_rows": 0,
                    },
                }
            ]
        },
    )

    report = build_report(_args(tmp_path, provenance_paths=[provenance]))

    row = report["rows"][0]
    assert report["status"] == "PASS"
    assert row["final_decision"] == "keep_quarantined_ohlcv_only_evidence_insufficient"
    assert row["reason"] == "preserve me"
    assert row["roll_window_synthetic_rows"] == 1
    assert row["symbol_change_synthetic_rows"] == 0
    assert row["instrument_id_change_synthetic_rows"] == 0


def test_access_window_local_trades_pass_promotes_historical_rows_to_usable(tmp_path: Path) -> None:
    _write_base_decisions(tmp_path / "reports" / "decisions.json")
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(
        provenance,
        {
            "entries": [
                {
                    "market": "ES",
                    "year": 2023,
                    "continuity": {
                        "roll_window_synthetic_rows": 0,
                        "symbol_change_synthetic_rows": 0,
                        "instrument_id_change_synthetic_rows": 0,
                    },
                }
            ]
        },
    )
    local_trades = tmp_path / "reports" / "local_trades.json"
    _write_local_trades_gap_report(local_trades)

    report = build_report(
        _args(tmp_path, provenance_paths=[provenance], local_trades_paths=[local_trades])
    )

    row = report["rows"][0]
    assert row["final_decision"] == "acceptable_with_caveat_ohlcv_empty_minutes_assumed"
    assert row["provenance_decision"] == "local_trades_access_window_validated_ohlcv_convention"
    assert row["local_trades_gap_validation_scope"] == "market_access_window_to_dataset_inference"
    assert row["local_trades_gap_validation_years"] == [2025, 2026]
    assert row["local_trades_gap_wfa_usable"] is True
    assert row["local_trades_gap_stop_reason"] is None
    assert report["decision_counts"] == {"acceptable_with_caveat_ohlcv_empty_minutes_assumed": 1}
    assert report["local_trades_schema_access"]["start"] == "2025-06-18T00:00:00Z"
    assert report["local_trades_schema_access"]["end"] == "2026-06-13T00:00:00Z"


def test_mixed_market_access_window_report_promotes_only_passing_markets(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "decisions.json",
        {"rows": [_base_decision("ES", 2023), _base_decision("ZN", 2023)]},
    )
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(
        provenance,
        {
            "entries": [
                {
                    "market": market,
                    "year": 2023,
                    "continuity": {
                        "roll_window_synthetic_rows": 0,
                        "symbol_change_synthetic_rows": 0,
                        "instrument_id_change_synthetic_rows": 0,
                    },
                }
                for market in ("ES", "ZN")
            ]
        },
    )
    local_trades = tmp_path / "reports" / "mixed_local_trades.json"
    _write_json(
        local_trades,
        {
            "status": "FAIL",
            "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
            "market_years": [
                {
                    "market": market,
                    "year": year,
                    "status": "PASS" if market == "ES" else "FAIL",
                    "summary": {
                        "missing_minute_count": 4,
                        "verified_empty_minutes": 4 if market == "ES" else 3,
                        "failed_minutes": 0 if market == "ES" else 1,
                        "unverified_minutes": 0,
                        "trade_rows_scanned": 100,
                        "archives_read": 1,
                    },
                }
                for market in ("ES", "ZN")
                for year in (2025, 2026)
            ],
        },
    )

    report = build_report(
        _args(tmp_path, provenance_paths=[provenance], local_trades_paths=[local_trades])
    )

    rows = {row["market"]: row for row in report["rows"]}
    assert rows["ES"]["final_decision"] == "acceptable_with_caveat_ohlcv_empty_minutes_assumed"
    assert rows["ES"]["local_trades_gap_wfa_usable"] is True
    assert rows["ZN"]["final_decision"] == "keep_quarantined_ohlcv_only_evidence_insufficient"
    assert rows["ZN"]["local_trades_gap_wfa_usable"] is False
    assert "failed_minutes=1" in rows["ZN"]["local_trades_gap_stop_reason"]


def test_local_trades_evidence_must_be_exact_complete_and_passing(tmp_path: Path) -> None:
    _write_base_decisions(tmp_path / "reports" / "decisions.json")
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(provenance, {"entries": []})
    partial = tmp_path / "reports" / "partial_local_trades.json"
    _write_local_trades_gap_report(
        partial,
        start="2025-06-19T00:00:00Z",
        end="2026-06-13T00:00:00Z",
    )
    failed = tmp_path / "reports" / "failed_local_trades.json"
    _write_local_trades_gap_report(failed, status="FAIL", failed=1, verified=3)
    unverified = tmp_path / "reports" / "unverified_local_trades.json"
    _write_local_trades_gap_report(unverified, verified=3, unverified=1)
    missing_slice = tmp_path / "reports" / "missing_slice_local_trades.json"
    _write_local_trades_gap_report(missing_slice, years=[2025])
    mismatched = tmp_path / "reports" / "mismatched_local_trades.json"
    _write_local_trades_gap_report(mismatched, market="CL")

    for local_trades in (partial, failed, unverified, missing_slice, mismatched):
        report = build_report(
            _args(tmp_path, provenance_paths=[provenance], local_trades_paths=[local_trades])
        )
        row = report["rows"][0]
        assert row["final_decision"] == "keep_quarantined_ohlcv_only_evidence_insufficient"
        assert row["local_trades_gap_wfa_usable"] is False
        assert row["local_trades_gap_stop_reason"]


def test_missing_provenance_counts_remain_null_without_inference(tmp_path: Path) -> None:
    _write_base_decisions(tmp_path / "reports" / "decisions.json")
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(provenance, {"entries": []})

    report = build_report(_args(tmp_path, provenance_paths=[provenance]))

    row = report["rows"][0]
    assert report["status"] == "PASS"
    assert report["missing_count_market_years"] == ["ES 2023"]
    assert row["roll_window_synthetic_rows"] is None
    assert row["symbol_change_synthetic_rows"] is None
    assert row["instrument_id_change_synthetic_rows"] is None


def test_main_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_base_decisions(tmp_path / "reports" / "decisions.json")
    provenance = tmp_path / "reports" / "provenance.json"
    _write_json(
        provenance,
        {
            "entries": [
                {
                    "market": "ES",
                    "year": 2023,
                    "continuity": {
                        "roll_window_synthetic_rows": 2,
                        "symbol_change_synthetic_rows": 0,
                        "instrument_id_change_synthetic_rows": 0,
                    },
                }
            ]
        },
    )

    code = main(
        [
            "--decision-table-json",
            str(tmp_path / "reports" / "decisions.json"),
            "--provenance-json",
            str(provenance),
            "--json-out",
            str(tmp_path / "reports" / "decisions_out.json"),
            "--md-out",
            str(tmp_path / "reports" / "decisions_out.md"),
        ]
    )

    assert code == 0
    assert (tmp_path / "reports" / "decisions_out.json").exists()
    assert (tmp_path / "reports" / "decisions_out.md").exists()
