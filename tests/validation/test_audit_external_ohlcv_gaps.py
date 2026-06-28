from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.validation.audit_external_ohlcv_gaps import build_report, main


def _write_session_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "session_templates:",
                "  cme_globex_17_16_ct:",
                "    timezone: America/Chicago",
                '    regular_open: "17:00"',
                '    regular_close: "16:00"',
                "    holidays: []",
                "    closed_dates: []",
                "    early_closes: {}",
                "markets:",
                "  default:",
                "    session_template: cme_globex_17_16_ct",
                "  ZN:",
                "    session_template: cme_globex_17_16_ct",
            ]
        ),
        encoding="utf-8",
    )


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_inputs(tmp_path: Path) -> None:
    _write_session_config(tmp_path / "configs" / "market_sessions.yaml")
    _write_parquet(
        tmp_path / "data" / "raw" / "ZN" / "2024.parquet",
        [
            {
                "ts_event": "2024-01-03T14:59:00Z",
                "raw_symbol": "ZNH4",
                "instrument_id": 123,
            },
            {
                "ts_event": "2024-01-03T15:04:00Z",
                "raw_symbol": "ZNH4",
                "instrument_id": 123,
            },
        ],
    )
    _write_parquet(
        tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet",
        [
            {
                "ts": "2024-01-03T14:59:00Z",
                "is_synthetic": False,
            },
            {
                "ts": "2024-01-03T15:00:00Z",
                "is_synthetic": True,
                "synthetic_gap_id": 7,
                "synthetic_gap_size_minutes": 4,
            },
            {
                "ts": "2024-01-03T15:01:00Z",
                "is_synthetic": True,
                "synthetic_gap_id": 7,
                "synthetic_gap_size_minutes": 4,
            },
            {
                "ts": "2024-01-03T15:04:00Z",
                "is_synthetic": False,
            },
        ],
    )


def _args(tmp_path: Path) -> object:
    return type(
        "Args",
        (),
        {
            "markets": ["ZN"],
            "years": [2024],
            "raw_root": str(tmp_path / "data" / "raw"),
            "causal_root": str(tmp_path / "data" / "causally_gated_normalized"),
            "session_config": str(tmp_path / "configs" / "market_sessions.yaml"),
            "external_root": str(tmp_path / "data" / "external_ohlcv_gap_checks"),
            "max_windows_per_market_year": 2,
            "buffer_minutes": 2,
            "require_external": False,
        },
    )()


def _manifest_args(tmp_path: Path, external: Path, manifest: Path | None = None) -> object:
    return type(
        "Args",
        (),
        {
            "manifest_json": str(manifest or tmp_path / "reports" / "manifest.json"),
            "external_ohlcv": [str(external)],
            "markets": None,
            "years": None,
            "external_market": None,
            "external_year": None,
            "external_contract": None,
            "external_instrument_id": None,
            "external_market_column": None,
            "external_year_column": None,
            "external_contract_column": None,
            "external_instrument_id_column": None,
            "external_volume_column": None,
        },
    )()


def _write_manifest(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "windows": [
                    {
                        "market": "ZN",
                        "year": 2024,
                        "synthetic_gap_id": "gap-1",
                        "raw_symbol": "ZNH4",
                        "instrument_id": 123,
                        "first_missing_ts_utc": "2024-01-03T15:00:00Z",
                        "last_missing_ts_utc": "2024-01-03T15:01:00Z",
                        "query_start_utc": "2024-01-03T14:59:00Z",
                        "query_end_utc": "2024-01-03T15:02:00Z",
                        "source_gap_timestamps": [
                            "2024-01-03T15:00:00Z",
                            "2024-01-03T15:01:00Z",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_external(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_builds_plan_and_resolves_adjacent_contract(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    report = build_report(_args(tmp_path))
    task = report["tasks"][0]

    assert report["status"] == "PASS"
    assert task["raw_symbol"] == "ZNH4"
    assert task["instrument_id"] == 123
    assert task["contract_resolution_status"] == "resolved"
    assert task["external_status"] == "missing_external_csv"
    assert task["decision"] == "needs_external_ohlcv_export"


def test_external_csv_with_gap_bar_keeps_quarantine(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    first = build_report(_args(tmp_path))["tasks"][0]
    csv_path = Path(first["external_csv_expected"])
    if not csv_path.is_absolute():
        csv_path = tmp_path / csv_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ts": "2024-01-03T15:00:00Z", "open": 1.0}]).to_csv(csv_path, index=False)
    args = _args(tmp_path)
    args.external_root = str(csv_path.parent)

    task = build_report(args)["tasks"][0]

    assert task["external_status"] == "external_ohlcv_bar_present_in_gap"
    assert task["decision"] == "external_source_disagrees_keep_quarantined_or_backfill"
    assert task["external_bar_count_in_gap"] == 1


def test_external_csv_without_gap_bar_supports_empty_minute_assumption(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    first = build_report(_args(tmp_path))["tasks"][0]
    csv_path = Path(first["external_csv_expected"])
    if not csv_path.is_absolute():
        csv_path = tmp_path / csv_path
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ts": "2024-01-03T14:59:00Z", "open": 1.0}]).to_csv(csv_path, index=False)
    args = _args(tmp_path)
    args.external_root = str(csv_path.parent)

    task = build_report(args)["tasks"][0]

    assert task["external_status"] == "external_ohlcv_bar_absent_in_gap"
    assert task["decision"] == "external_ohlcv_absence_supports_empty_minute_assumption_for_sample"
    assert task["external_bar_count_in_gap"] == 0


def test_require_external_fails_when_csv_missing(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    args = _args(tmp_path)
    args.require_external = True

    report = build_report(args)

    assert report["status"] == "FAIL"
    assert "required external CSV exports are missing" in report["failures"]


def test_missing_inputs_fail_closed_after_writing_reports(tmp_path: Path) -> None:
    _write_session_config(tmp_path / "configs" / "market_sessions.yaml")
    json_out = tmp_path / "reports" / "external.json"
    md_out = tmp_path / "reports" / "external.md"

    code = main(
        [
            "--markets",
            "ZN",
            "--years",
            "2024",
            "--raw-root",
            str(tmp_path / "data" / "raw"),
            "--causal-root",
            str(tmp_path / "data" / "causally_gated_normalized"),
            "--session-config",
            str(tmp_path / "configs" / "market_sessions.yaml"),
            "--external-root",
            str(tmp_path / "data" / "external_ohlcv_gap_checks"),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 1
    assert report["status"] == "FAIL"
    assert "missing input" in " ".join(report["failures"])
    assert md_out.exists()


def test_main_requires_explicit_causal_root_in_scan_mode(tmp_path: Path) -> None:
    json_out = tmp_path / "reports" / "external.json"
    md_out = tmp_path / "reports" / "external.md"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--markets",
                "ZN",
                "--years",
                "2024",
                "--raw-root",
                str(tmp_path / "data" / "raw"),
                "--session-config",
                str(tmp_path / "configs" / "market_sessions.yaml"),
                "--external-root",
                str(tmp_path / "data" / "external_ohlcv_gap_checks"),
                "--json-out",
                str(json_out),
                "--md-out",
                str(md_out),
            ]
        )

    assert exc_info.value.code == 2
    assert not json_out.exists()
    assert not md_out.exists()


def test_manifest_mode_classifies_present_external_gap_bar(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    external = tmp_path / "external.csv"
    _write_manifest(manifest)
    _write_external(
        external,
        [
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T14:59:00Z",
                "volume": 10,
            },
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T15:00:00Z",
                "volume": 5,
            },
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T15:02:00Z",
                "volume": 12,
            },
        ],
    )

    report = build_report(_manifest_args(tmp_path, external, manifest))
    window = report["windows"][0]

    assert report["status"] == "PASS"
    assert window["classification"] == "confirmed_present_in_external_ohlcv"
    assert window["external_bar_count_in_gap"] == 1


def test_manifest_mode_classifies_missing_in_both_sources(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    external = tmp_path / "external.csv"
    _write_manifest(manifest)
    _write_external(
        external,
        [
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T14:59:00Z",
                "volume": 10,
            },
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T15:02:00Z",
                "volume": 12,
            },
        ],
    )

    report = build_report(_manifest_args(tmp_path, external, manifest))

    assert report["status"] == "PASS"
    assert report["windows"][0]["classification"] == "missing_in_both_ohlcv_sources"


def test_manifest_mode_classifies_zero_volume_external_bar(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    external = tmp_path / "external.csv"
    _write_manifest(manifest)
    _write_external(
        external,
        [
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T14:59:00Z",
                "volume": 10,
            },
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T15:00:00Z",
                "volume": 0,
            },
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNH4",
                "ts": "2024-01-03T15:02:00Z",
                "volume": 12,
            },
        ],
    )

    report = build_report(_manifest_args(tmp_path, external, manifest))

    assert report["status"] == "PASS"
    assert report["windows"][0]["classification"] == "external_zero_volume_bar"


def test_manifest_mode_fails_closed_on_contract_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    external = tmp_path / "external.csv"
    _write_manifest(manifest)
    _write_external(
        external,
        [
            {
                "market": "ZN",
                "year": 2024,
                "raw_symbol": "ZNM4",
                "ts": "2024-01-03T15:00:00Z",
                "volume": 5,
            }
        ],
    )

    report = build_report(_manifest_args(tmp_path, external, manifest))

    assert report["status"] == "FAIL"
    assert report["windows"][0]["classification"] == "contract_or_session_mismatch"


def test_manifest_mode_fails_closed_on_missing_manifest(tmp_path: Path) -> None:
    external = tmp_path / "external.csv"
    _write_external(
        external,
        [{"market": "ZN", "year": 2024, "raw_symbol": "ZNH4", "ts": "2024-01-03T15:00:00Z"}],
    )

    report = build_report(_manifest_args(tmp_path, external))

    assert report["status"] == "FAIL"
    assert "missing manifest" in " ".join(report["failures"])


def test_manifest_mode_main_writes_reports(tmp_path: Path) -> None:
    manifest = tmp_path / "reports" / "manifest.json"
    external = tmp_path / "external.csv"
    json_out = tmp_path / "reports" / "external_compare.json"
    md_out = tmp_path / "reports" / "external_compare.md"
    _write_manifest(manifest)
    _write_external(
        external,
        [
            {"market": "ZN", "year": 2024, "raw_symbol": "ZNH4", "ts": "2024-01-03T14:59:00Z"},
            {"market": "ZN", "year": 2024, "raw_symbol": "ZNH4", "ts": "2024-01-03T15:02:00Z"},
        ],
    )

    code = main(
        [
            "--manifest-json",
            str(manifest),
            "--external-ohlcv",
            str(external),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 0
    assert report["windows"][0]["classification"] == "missing_in_both_ohlcv_sources"
    assert md_out.exists()
