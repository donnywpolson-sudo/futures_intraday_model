from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from scripts.validation.build_data_audit_universe import build_universe, main


def _write_profile_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_1_research:",
                "    markets: [ES, CL]",
                "    years: [2022, 2023]",
                "aliases:",
                "  tier_1: tier_1_research",
            ]
        ),
        encoding="utf-8",
    )


def _write_decisions(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def _args(
    tmp_path: Path,
    *,
    decision_path: Path | None = None,
    diagnostics: list[str] | None = None,
    accept_databento_convention: bool = False,
) -> Namespace:
    return Namespace(
        decision_table_json=str(decision_path or tmp_path / "reports" / "decisions.json"),
        profile="tier_1",
        profile_config=str(tmp_path / "configs" / "alpha_tiered.yaml"),
        diagnostic_only_markets=diagnostics or [],
        json_out=str(tmp_path / "reports" / "universe.json"),
        md_out=str(tmp_path / "reports" / "universe.md"),
        require_usable=False,
        accept_databento_ohlcv_no_trade_convention=accept_databento_convention,
    )


def _complete_rows() -> list[dict[str, object]]:
    return [
        {
            "market": "ES",
            "year": 2022,
            "final_decision": "acceptable_with_caveat_ohlcv_empty_minutes_assumed",
            "reason": "accepted with caveat",
            "missing_minutes": 16,
            "largest_gap_size_minutes": 2,
            "active_session_synthetic_rows": 0,
            "failures": [],
        },
        {
            "market": "ES",
            "year": 2023,
            "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
            "reason": "quarantine",
            "missing_minutes": 10,
            "largest_gap_size_minutes": 3,
            "active_session_synthetic_rows": 0,
            "missing_minute_status": "PASS",
            "provenance_status": "PASS",
            "provenance_decision_reasons": [
                "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes",
                "synthetic timestamps are absent from raw OHLCV parquet",
            ],
            "failures": [],
        },
        {
            "market": "CL",
            "year": 2022,
            "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
            "reason": "quarantine",
            "missing_minutes": 20,
            "largest_gap_size_minutes": 4,
            "active_session_synthetic_rows": 2,
            "missing_minute_status": "PASS",
            "provenance_status": "PASS",
            "provenance_decision_reasons": [
                "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes",
                "synthetic timestamps are absent from raw OHLCV parquet",
                "active-session synthetic share 0.200000 exceeds ceiling 0.050000",
            ],
            "failures": [],
        },
        {
            "market": "CL",
            "year": 2023,
            "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
            "reason": "quarantine",
            "missing_minutes": 30,
            "largest_gap_size_minutes": 5,
            "active_session_synthetic_rows": 3,
            "failures": [],
        },
    ]


def test_builds_usable_and_quarantined_universe(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows())

    report = build_universe(_args(tmp_path))

    assert report["status"] == "PASS"
    assert report["summary"]["audit_status_counts"] == {"quarantined": 3, "usable": 1}
    usable = report["summary"]["usable_market_years"]
    assert usable == [{"market": "ES", "year": 2022}]


def test_diagnostic_market_override_is_explicit(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows())

    report = build_universe(_args(tmp_path, diagnostics=["CL"]))

    assert report["status"] == "PASS"
    assert report["summary"]["audit_status_counts"] == {
        "diagnostic_only": 2,
        "quarantined": 1,
        "usable": 1,
    }


def test_databento_ohlcv_convention_can_relax_ohlcv_only_quarantine(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows())

    report = build_universe(_args(tmp_path, accept_databento_convention=True))

    assert report["status"] == "PASS"
    assert report["summary"]["audit_status_counts"] == {"quarantined": 1, "usable": 3}
    row = next(item for item in report["market_years"] if item["market"] == "ES" and item["year"] == 2023)
    assert row["audit_status"] == "usable"
    assert "Databento documents ohlcv-1m" in row["reason"]
    assert "matching DBN manifests" in row["reason"]
    assert report["policy"]["databento_ohlcv_no_trade_convention"]["enabled"] is True


def test_databento_ohlcv_convention_does_not_block_on_gap_size_or_share_flags(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows())

    report = build_universe(_args(tmp_path, accept_databento_convention=True))

    row = next(item for item in report["market_years"] if item["market"] == "CL" and item["year"] == 2022)
    assert row["audit_status"] == "usable"
    assert "Databento documents ohlcv-1m" in row["reason"]


def test_databento_ohlcv_convention_allows_roll_window_only_when_counts_are_available(tmp_path: Path) -> None:
    rows = _complete_rows()
    rows[1]["provenance_decision_reasons"] = [
        "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes",
        "synthetic timestamps are absent from raw OHLCV parquet",
        "synthetic rows overlap roll/symbol/instrument-change evidence",
    ]
    rows[1]["roll_window_synthetic_rows"] = 2
    rows[1]["symbol_change_synthetic_rows"] = 0
    rows[1]["instrument_id_change_synthetic_rows"] = 0
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", rows)

    report = build_universe(_args(tmp_path, accept_databento_convention=True))

    row = next(item for item in report["market_years"] if item["market"] == "ES" and item["year"] == 2023)
    assert row["audit_status"] == "usable"


def test_databento_ohlcv_convention_fails_closed_when_roll_counts_are_missing(tmp_path: Path) -> None:
    rows = _complete_rows()
    rows[1]["provenance_decision_reasons"] = [
        "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes",
        "synthetic timestamps are absent from raw OHLCV parquet",
        "synthetic rows overlap roll/symbol/instrument-change evidence",
    ]
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", rows)

    report = build_universe(_args(tmp_path, accept_databento_convention=True))

    row = next(item for item in report["market_years"] if item["market"] == "ES" and item["year"] == 2023)
    assert row["audit_status"] == "quarantined"
    assert "lacks separate counts" in row["reason"]


def test_databento_ohlcv_convention_blocks_direct_symbol_or_instrument_changes(tmp_path: Path) -> None:
    rows = _complete_rows()
    rows[1]["provenance_decision_reasons"] = [
        "L1/trades unavailable: OHLCV-only audit cannot prove no trades occurred inside missing minutes",
        "synthetic timestamps are absent from raw OHLCV parquet",
        "synthetic rows overlap roll/symbol/instrument-change evidence",
    ]
    rows[1]["roll_window_synthetic_rows"] = 2
    rows[1]["symbol_change_synthetic_rows"] = 1
    rows[1]["instrument_id_change_synthetic_rows"] = 0
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", rows)

    report = build_universe(_args(tmp_path, accept_databento_convention=True))

    row = next(item for item in report["market_years"] if item["market"] == "ES" and item["year"] == 2023)
    assert row["audit_status"] == "quarantined"
    assert "symbol_change_synthetic_rows=1" in row["reason"]


def test_missing_decision_row_fails_closed(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows()[:-1])

    report = build_universe(_args(tmp_path))

    assert report["status"] == "FAIL"
    assert "missing decision row for CL 2023" in report["failures"]
    row = next(item for item in report["market_years"] if item["market"] == "CL" and item["year"] == 2023)
    assert row["audit_status"] == "quarantined"


def test_main_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_decisions(tmp_path / "reports" / "decisions.json", _complete_rows())
    json_out = tmp_path / "reports" / "universe.json"
    md_out = tmp_path / "reports" / "universe.md"

    code = main(
        [
            "--decision-table-json",
            str(tmp_path / "reports" / "decisions.json"),
            "--profile",
            "tier_1",
            "--profile-config",
            str(tmp_path / "configs" / "alpha_tiered.yaml"),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 0
    assert report["summary"]["audit_status_counts"]["usable"] == 1
    assert md_out.exists()
