from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation.audit_tick_source_gap_downloads import build_report, main


def _estimate_payload(cost: float = 0.001) -> dict[str, object]:
    return {
        "status": "PASS",
        "api_called": True,
        "download_allowed": False,
        "total_estimated_cost_usd": cost,
        "estimates": [
            {
                "status": "ok",
                "market": "ZN",
                "year": 2024,
                "dataset": "GLBX.MDP3",
                "schema": "trades",
                "stype_in": "instrument_id",
                "symbols": "123",
                "start": "2024-01-02T23:01:00Z",
                "end": "2024-01-02T23:03:00Z",
                "source_gap_timestamps": {
                    "first_synthetic_ts": "2024-01-02T23:01:00Z",
                    "last_synthetic_ts": "2024-01-02T23:02:00Z",
                },
            }
        ],
    }


class FakeStore:
    def to_df(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ts_event": "2024-01-02T23:01:30Z", "price": 100.0, "size": 1},
                {"ts_event": "2024-01-02T23:04:00Z", "price": 100.25, "size": 1},
            ]
        )


class FakeTimeseries:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_range(self, **kwargs: object) -> FakeStore:
        self.calls.append(kwargs)
        return FakeStore()


class FakeClient:
    def __init__(self) -> None:
        self.timeseries = FakeTimeseries()


class FailingTimeseries:
    def get_range(self, **_: object) -> object:
        raise RuntimeError("network blocked")


class FailingClient:
    def __init__(self) -> None:
        self.timeseries = FailingTimeseries()


def test_refuses_download_without_flag(tmp_path: Path) -> None:
    report = build_report(
        _estimate_payload(),
        estimate_path=tmp_path / "estimate.json",
        output_root=tmp_path / "data" / "source_gap_audit",
        max_total_cost_usd=0.01,
        allow_download=False,
        client=FakeClient(),
    )

    assert report["status"] == "FAIL"
    assert report["download_api_called"] is False
    assert "--allow-download is required" in report["failures"]


def test_downloads_and_counts_activity_inside_gap(tmp_path: Path) -> None:
    client = FakeClient()
    report = build_report(
        _estimate_payload(),
        estimate_path=tmp_path / "estimate.json",
        output_root=tmp_path / "data" / "source_gap_audit",
        max_total_cost_usd=0.01,
        allow_download=True,
        client=client,
    )
    audit = report["audits"][0]

    assert report["status"] == "PASS"
    assert report["download_api_called"] is True
    assert client.timeseries.calls[0]["schema"] == "trades"
    assert client.timeseries.calls[0]["stype_in"] == "instrument_id"
    assert audit["downloaded_rows"] == 2
    assert audit["rows_inside_ohlcv_gap"] == 1
    assert audit["has_trade_or_book_activity_inside_gap"] is True
    assert (tmp_path / audit["output_path"]).exists()


def test_rejects_cost_above_ceiling(tmp_path: Path) -> None:
    report = build_report(
        _estimate_payload(cost=10.0),
        estimate_path=tmp_path / "estimate.json",
        output_root=tmp_path / "data" / "source_gap_audit",
        max_total_cost_usd=0.01,
        allow_download=True,
        client=FakeClient(),
    )

    assert report["status"] == "FAIL"
    assert report["download_api_called"] is False
    assert "exceeds max" in report["failures"][0]


def test_download_error_fails_closed_in_report(tmp_path: Path) -> None:
    report = build_report(
        _estimate_payload(),
        estimate_path=tmp_path / "estimate.json",
        output_root=tmp_path / "data" / "source_gap_audit",
        max_total_cost_usd=0.01,
        allow_download=True,
        client=FailingClient(),
    )

    assert report["status"] == "FAIL"
    assert report["download_api_called"] is True
    assert "network blocked" in report["failures"][0]
    assert report["audits"] == []


def test_main_writes_fail_closed_report_for_missing_estimate(tmp_path: Path) -> None:
    report_out = tmp_path / "reports" / "download_audit.json"

    code = main(
        [
            "--cost-estimate-json",
            str(tmp_path / "missing.json"),
            "--output-root",
            str(tmp_path / "data" / "source_gap_audit"),
            "--report-out",
            str(report_out),
        ]
    )

    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert code == 1
    assert report["status"] == "FAIL"
    assert "missing input" in report["failures"][0]
