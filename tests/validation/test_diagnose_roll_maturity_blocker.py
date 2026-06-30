from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.validation import diagnose_roll_maturity_blocker as diag


def _write_raw(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _roll_rows() -> list[dict[str, object]]:
    base = {
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 1,
        "source_file": "data/dbn/ohlcv_1m/6M/2012/2012-01-01_2013-01-01.dbn.zst",
        "status_missing": False,
        "statistics_missing": False,
    }
    return [
        {
            **base,
            "ts_event": "2012-12-14T00:10:00Z",
            "instrument_id": 36659,
            "raw_symbol": "6MH3",
            "maturity_year": 2013,
            "maturity_month": 3,
        },
        {
            **base,
            "ts_event": "2012-12-14T00:11:00Z",
            "instrument_id": 94268,
            "raw_symbol": "6MZ2",
            "maturity_year": 2012,
            "maturity_month": 12,
        },
    ]


def _write_readiness(path: Path, *, backsteps: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "blocker_count": 1,
                "blockers": [
                    {
                        "market": "6M",
                        "year": 2012,
                        "status": "WARN",
                        "top_blocker_reason": f"roll maturity sequence not monotonic: backsteps={backsteps}",
                        "warnings": [
                            f"roll maturity sequence not monotonic: backsteps={backsteps}",
                            "synthetic threshold breached: rows_pct=46.563343 max_gap_minutes=116",
                        ],
                        "roll_maturity_backstep_count": backsteps,
                        "roll_maturity_backstep_examples": [
                            {
                                "ts": "2012-12-14T00:11:00+00:00",
                                "previous_raw_symbol": "6MH3",
                                "current_raw_symbol": "6MZ2",
                                "previous_maturity": 24159,
                                "current_maturity": 24156,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_roll_maturity_backstep_confirmed_from_raw_ts_event(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    _write_raw(raw_root / "6M" / "2012.parquet", _roll_rows())
    _write_readiness(readiness)

    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    assert report["status"] == "PASS"
    assert report["disposition_call"] == "roll_maturity_backstep_confirmed_in_raw"
    assert report["computed_backstep_count"] == 1
    assert report["computed_matches_readiness"] is True
    assert report["status_missing_rows"] == 0
    assert report["statistics_missing_rows"] == 0


def test_vendor_continuous_identity_proof_changes_disposition_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def proof(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "status": "PASS",
            "policy": "databento_continuous_roll_identity_proven",
            "identity_mismatch_counts": {},
            "failures": [],
        }

    monkeypatch.setattr(diag, "_vendor_continuous_roll_backstep_identity_evidence", proof)
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    _write_raw(raw_root / "6M" / "2012.parquet", _roll_rows())
    _write_readiness(readiness)

    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    assert report["status"] == "PASS"
    assert report["disposition_call"] == "vendor_continuous_roll_backstep_policy_mismatch"
    assert report["vendor_continuous_identity_evidence"]["status"] == "PASS"


def test_readiness_disagrees_when_backstep_count_differs(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    _write_raw(raw_root / "6M" / "2012.parquet", _roll_rows())
    _write_readiness(readiness, backsteps=2)

    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    assert report["status"] == "FAIL"
    assert report["disposition_call"] == "readiness_logic_disagrees_with_raw"
    assert report["computed_backstep_count"] == 1
    assert report["readiness_roll_maturity_backstep_count"] == 2


def test_missing_roll_metadata_columns_are_reported(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    rows = _roll_rows()
    for row in rows:
        row.pop("maturity_month")
    _write_raw(raw_root / "6M" / "2012.parquet", rows)
    _write_readiness(readiness)

    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    assert report["status"] == "FAIL"
    assert report["disposition_call"] == "missing_roll_metadata_columns"
    assert report["missing_roll_metadata_columns"] == ["maturity_month"]


def test_disposition_request_keeps_build_gate_closed(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    diagnosis = tmp_path / "diagnosis.json"
    _write_raw(raw_root / "6M" / "2012.parquet", _roll_rows())
    _write_readiness(readiness)
    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    request = diag.build_disposition_request(report, diagnosis_path=diagnosis)

    assert request["status"] == "AWAITING_HUMAN_6M_2012_DISPOSITION"
    assert request["selected_disposition"] == "NONE_SELECTED"
    assert request["build_execution_allowed_now"] is False
    assert request["broader_modeling_approved"] is False
    assert request["config_promotion_approved"] is False
    assert request["research_use_allowed"] is False
    assert "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY" in request["allowed_disposition_tokens"]


def test_disposition_request_accepts_fail_closed_resolution(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    readiness = tmp_path / "readiness.json"
    diagnosis = tmp_path / "diagnosis.json"
    _write_raw(raw_root / "6M" / "2012.parquet", _roll_rows())
    _write_readiness(readiness)
    report = diag.build_report(
        market="6M",
        year=2012,
        raw_root=raw_root,
        readiness_json=readiness,
    )

    request = diag.build_disposition_request(
        report,
        diagnosis_path=diagnosis,
        selected_disposition="KEEP_6M_2012_FAIL_CLOSED_NO_BUILD",
    )

    assert request["status"] == "RESOLVED_6M_2012_FAIL_CLOSED_NO_BUILD"
    assert request["selected_disposition"] == "KEEP_6M_2012_FAIL_CLOSED_NO_BUILD"
    assert request["recommended_default"] == "KEEP_6M_2012_FAIL_CLOSED_NO_BUILD"
    assert request["build_execution_allowed_now"] is False
    assert request["broader_modeling_approved"] is False
    assert request["config_promotion_approved"] is False
    assert request["research_use_allowed"] is False


def test_disposition_request_rejects_unknown_selected_disposition(tmp_path: Path) -> None:
    report = {"market": "6M", "year": 2012, "forbidden_actions_performed": {}}

    with pytest.raises(ValueError, match="unsupported selected disposition"):
        diag.build_disposition_request(
            report,
            diagnosis_path=tmp_path / "diagnosis.json",
            selected_disposition="APPROVE_UNKNOWN",
        )
