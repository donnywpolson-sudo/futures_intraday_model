from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.validation.audit_ohlcv_provenance_continuity import build_report, main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _write_dbn_with_manifest(root: Path, schema_dir: str, schema: str, *, market: str = "ZN", year: int = 2024) -> Path:
    path = root / schema_dir / market / str(year) / f"{year}-01-01_{year + 1}-01-01.dbn.zst"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{schema}-{market}-{year}".encode("utf-8"))
    digest = _sha256(path)
    payload = {
        "vendor": "databento",
        "dataset": "GLBX.MDP3",
        "schema": schema,
        "market": market,
        "symbols_requested": [f"{market}.v.0" if schema == "ohlcv-1m" else f"{market}.FUT"],
        "start": f"{year}-01-01",
        "end": f"{year + 1}-01-01",
        "stype_in": "continuous" if schema == "ohlcv-1m" else "parent",
        "stype_out": "instrument_id",
        "encoding": "dbn",
        "compression": "zstd",
        "downloaded_at": "2026-06-15T00:00:00+00:00",
        "path": path.as_posix(),
        "file_size_bytes": path.stat().st_size,
        "file_sha256": digest,
        "job_id": "fixture",
        "api_client_version": "0.79.0",
        "request_status": "ok",
    }
    path.with_name(f"{path.name}.manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return path


def _args(tmp_path: Path) -> object:
    return type(
        "Args",
        (),
        {
            "markets": ["ZN"],
            "years": [2024],
            "raw_root": str(tmp_path / "data" / "raw"),
            "causal_root": str(tmp_path / "data" / "causally_gated_normalized"),
            "dbn_root": str(tmp_path / "data" / "dbn"),
            "session_config": str(tmp_path / "configs" / "market_sessions.yaml"),
            "max_synthetic_row_share": 0.01,
            "max_active_session_gap_share": 0.05,
            "max_gap_minutes_for_accept": 5,
        },
    )()


def _write_base_inputs(tmp_path: Path, *, synthetic_rows: list[dict[str, object]] | None = None) -> None:
    _write_session_config(tmp_path / "configs" / "market_sessions.yaml")
    ohlcv = _write_dbn_with_manifest(tmp_path / "data" / "dbn", "ohlcv_1m", "ohlcv-1m")
    _write_dbn_with_manifest(tmp_path / "data" / "dbn", "definition", "definition")
    raw_rows = [
        {
            "ts_event": "2024-01-02T23:00:00Z",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 10,
            "instrument_id": 1,
            "raw_symbol": "ZNH4",
            "tick_size": 0.015625,
            "source_file": ohlcv.as_posix(),
            "source_sha256": _sha256(ohlcv),
        },
        {
            "ts_event": "2024-01-03T15:05:00Z",
            "open": 101.0,
            "high": 101.0,
            "low": 101.0,
            "close": 101.0,
            "volume": 20,
            "instrument_id": 1,
            "raw_symbol": "ZNH4",
            "tick_size": 0.015625,
            "source_file": ohlcv.as_posix(),
            "source_sha256": _sha256(ohlcv),
        },
    ]
    _write_parquet(tmp_path / "data" / "raw" / "ZN" / "2024.parquet", raw_rows)
    causal_rows = [
        {
            "ts": "2024-01-02T23:00:00Z",
            "is_synthetic": False,
            "roll_window_flag": False,
            "symbol_change_flag": False,
            "instrument_id_change_flag": False,
        },
        {
            "ts": "2024-01-03T15:05:00Z",
            "is_synthetic": False,
            "roll_window_flag": False,
            "symbol_change_flag": False,
            "instrument_id_change_flag": False,
        },
    ]
    if synthetic_rows:
        causal_rows.extend(synthetic_rows)
    _write_parquet(tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet", causal_rows)


def test_provenance_passes_when_raw_source_matches_ohlcv_manifest(tmp_path: Path) -> None:
    _write_base_inputs(tmp_path)

    report = build_report(_args(tmp_path))
    entry = report["entries"][0]

    assert report["status"] == "PASS"
    assert entry["decision"] == "usable_no_synthetic_gaps_detected"
    assert entry["provenance"]["raw_source_matches_ohlcv_manifest"] is True
    assert entry["provenance"]["ohlcv_dbn"]["hash_matches_manifest"] is True
    assert entry["provenance"]["definition_dbn"]["hash_matches_manifest"] is True


def test_active_session_synthetic_gaps_keep_market_quarantined(tmp_path: Path) -> None:
    _write_base_inputs(
        tmp_path,
        synthetic_rows=[
            {
                "ts": "2024-01-03T15:00:00Z",
                "is_synthetic": True,
                "synthetic_gap_id": 1,
                "synthetic_gap_size_minutes": 6,
                "roll_window_flag": False,
                "symbol_change_flag": False,
                "instrument_id_change_flag": False,
            }
        ],
    )

    entry = build_report(_args(tmp_path))["entries"][0]

    assert entry["status"] == "PASS"
    assert entry["decision"] == "keep_quarantined_ohlcv_only_evidence_insufficient"
    assert entry["continuity"]["synthetic_timestamps_missing_from_raw"] == 1
    assert entry["continuity"]["active_session_synthetic_rows"] == 1


def test_low_liquidity_small_gaps_can_be_accepted_with_caveat(tmp_path: Path) -> None:
    _write_base_inputs(
        tmp_path,
        synthetic_rows=[
            {
                "ts": "2024-01-02T23:02:00Z",
                "is_synthetic": True,
                "synthetic_gap_id": 1,
                "synthetic_gap_size_minutes": 2,
                "roll_window_flag": False,
                "symbol_change_flag": False,
                "instrument_id_change_flag": False,
            }
        ],
    )
    args = _args(tmp_path)
    args.max_synthetic_row_share = 1.0

    entry = build_report(args)["entries"][0]

    assert entry["decision"] == "accept_with_caveat_ohlcv_empty_minutes_assumed"
    assert "cannot prove no trades" in " ".join(entry["decision_reasons"])


def test_missing_definition_dbn_fails_closed_after_writing_reports(tmp_path: Path) -> None:
    _write_base_inputs(tmp_path)
    for path in (tmp_path / "data" / "dbn" / "definition" / "ZN" / "2024").iterdir():
        path.unlink()
    json_out = tmp_path / "reports" / "ohlcv_audit.json"
    md_out = tmp_path / "reports" / "ohlcv_audit.md"

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
            "--dbn-root",
            str(tmp_path / "data" / "dbn"),
            "--session-config",
            str(tmp_path / "configs" / "market_sessions.yaml"),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 1
    assert report["status"] == "FAIL"
    assert "missing definition DBN file" in " ".join(report["failures"])
    assert md_out.exists()


def test_main_requires_explicit_causal_root(tmp_path: Path) -> None:
    json_out = tmp_path / "reports" / "ohlcv_audit.json"
    md_out = tmp_path / "reports" / "ohlcv_audit.md"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--markets",
                "ZN",
                "--years",
                "2024",
                "--raw-root",
                str(tmp_path / "data" / "raw"),
                "--dbn-root",
                str(tmp_path / "data" / "dbn"),
                "--session-config",
                str(tmp_path / "configs" / "market_sessions.yaml"),
                "--json-out",
                str(json_out),
                "--md-out",
                str(md_out),
            ]
        )

    assert exc_info.value.code == 2
    assert not json_out.exists()
    assert not md_out.exists()


def test_ohlcv_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    _write_base_inputs(tmp_path)
    ohlcv = next((tmp_path / "data" / "dbn" / "ohlcv_1m" / "ZN" / "2024").glob("*.dbn.zst"))
    ohlcv.write_bytes(b"changed")

    entry = build_report(_args(tmp_path))["entries"][0]

    assert entry["status"] == "FAIL"
    assert entry["decision"] == "blocked_missing_or_mismatched_provenance"
    assert any("DBN hash mismatch" in failure for failure in entry["failures"])
