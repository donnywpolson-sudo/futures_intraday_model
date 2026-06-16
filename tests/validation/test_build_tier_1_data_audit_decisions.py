from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from scripts.validation.build_tier_1_data_audit_decisions import build_report, main


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path, *, provenance_paths: list[Path]) -> Namespace:
    return Namespace(
        decision_table_json=str(tmp_path / "reports" / "decisions.json"),
        provenance_json=[str(path) for path in provenance_paths],
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
