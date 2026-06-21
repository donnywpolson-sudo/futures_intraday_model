from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.phase2_causal_base.build_causal_base_data import raw_alignment_guard_failures
from scripts.validation import build_sr_front_contract_candidate as builder


def _ohlcv_row(ts: str, instrument_id: int, symbol: str, close: float) -> dict[str, object]:
    return {
        "ts_event": pd.Timestamp(ts, tz="UTC"),
        "open": close - 0.01,
        "high": close + 0.01,
        "low": close - 0.02,
        "close": close,
        "volume": 10,
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": instrument_id,
        "symbol": symbol,
        "data_quality_status": "available",
        "data_quality_degraded": False,
    }


def _definition_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "ts_recv": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 1,
                "raw_symbol": "SR1H4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "contract_multiplier": 2500.0,
                "expiration": pd.Timestamp("2024-03-15T16:00:00Z"),
                "activation": pd.Timestamp("2023-12-01T00:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 3,
            },
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "ts_recv": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 2,
                "raw_symbol": "SR1M4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "contract_multiplier": 2500.0,
                "expiration": pd.Timestamp("2024-06-17T16:00:00Z"),
                "activation": pd.Timestamp("2023-12-01T00:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 6,
            },
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "ts_recv": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 99,
                "raw_symbol": "SR1H4-SR1M4",
                "instrument_class": "S",
                "min_price_increment": 0.0025,
                "contract_multiplier": 2500.0,
                "expiration": pd.Timestamp("2024-01-15T16:00:00Z"),
                "activation": pd.Timestamp("2023-12-01T00:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 1,
            },
        ]
    )


def _status_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2024-01-01T00:00:00Z"),
                "instrument_id": 1,
                "action": 7,
                "reason": "NORMAL",
                "trading_event": 0,
                "is_trading": "Y",
                "is_quoting": "Y",
            },
            {
                "ts_event": pd.Timestamp("2024-03-16T00:00:00Z"),
                "instrument_id": 2,
                "action": 7,
                "reason": "NORMAL",
                "trading_event": 0,
                "is_trading": "Y",
                "is_quoting": "Y",
            },
        ]
    )


def _statistics_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2024-01-01T00:00:00Z"),
                "instrument_id": 1,
                "stat_type": 1,
                "price": 95.0,
            },
            {
                "ts_event": pd.Timestamp("2024-03-16T00:00:00Z"),
                "instrument_id": 2,
                "stat_type": 1,
                "price": 96.0,
            },
        ]
    )


def test_front_contract_candidate_selects_front_and_drops_deferred_only_minutes() -> None:
    ohlcv = pd.DataFrame(
        [
            _ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.0),
            _ohlcv_row("2024-01-02T15:00:00Z", 2, "SR1M4", 96.0),
            _ohlcv_row("2024-01-02T15:00:00Z", 99, "SR1H4-SR1M4", 0.1),
            _ohlcv_row("2024-01-02T15:01:00Z", 2, "SR1M4", 96.1),
            _ohlcv_row("2024-03-16T15:00:00Z", 2, "SR1M4", 96.2),
        ]
    )

    candidate, metrics = builder.build_front_contract_candidate_frame(
        ohlcv=ohlcv,
        definitions=_definition_frame(),
        status=_status_frame(),
        statistics=_statistics_frame(),
        market="SR1",
        year=2024,
        source_files=["candidate.dbn.zst"],
        source_hashes=["a" * 64],
    )

    assert candidate["raw_symbol"].tolist() == ["SR1H4", "SR1M4"]
    assert candidate["instrument_id"].tolist() == [1, 2]
    assert metrics["raw_parent_ohlcv_rows"] == 5
    assert metrics["outright_ohlcv_rows"] == 4
    assert metrics["dropped_non_outright_rows"] == 1
    assert metrics["dropped_deferred_contract_rows"] == 2
    assert metrics["maturity_backstep_count"] == 0
    assert metrics["selected_symbol_counts"] == [
        {"raw_symbol": "SR1H4", "rows": 1},
        {"raw_symbol": "SR1M4", "rows": 1},
    ]
    assert candidate["status_missing"].eq(False).all()
    assert candidate["stat_opening_price_missing"].eq(False).all()
    assert candidate["source_file"].eq("candidate.dbn.zst").all()


def test_front_contract_candidate_rejects_duplicate_front_timestamps() -> None:
    ohlcv = pd.DataFrame(
        [
            _ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.0),
            _ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.1),
        ]
    )

    with pytest.raises(ValueError, match="duplicate timestamps"):
        builder.build_front_contract_candidate_frame(
            ohlcv=ohlcv,
            definitions=_definition_frame(),
            status=None,
            statistics=None,
            market="SR1",
            year=2024,
            source_files=["candidate.dbn.zst"],
            source_hashes=["a" * 64],
        )


def test_front_contract_candidate_rejects_backward_maturity_sequence() -> None:
    definitions = pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 1,
                "raw_symbol": "SR1M4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2024-01-10T00:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 6,
            },
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 2,
                "raw_symbol": "SR1H4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2024-02-10T00:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 3,
            },
        ]
    )
    ohlcv = pd.DataFrame(
        [
            _ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1M4", 96.0),
            _ohlcv_row("2024-01-11T15:00:00Z", 2, "SR1H4", 95.0),
        ]
    )

    with pytest.raises(ValueError, match="maturity sequence moved backward"):
        builder.build_front_contract_candidate_frame(
            ohlcv=ohlcv,
            definitions=definitions,
            status=None,
            statistics=None,
            market="SR1",
            year=2024,
            source_files=["candidate.dbn.zst"],
            source_hashes=["a" * 64],
        )


def test_maturity_backstep_count_handles_unsigned_integer_dtypes() -> None:
    frame = pd.DataFrame(
        {
            "maturity_year": pd.Series([2022, 2022], dtype="uint16"),
            "maturity_month": pd.Series([6, 5], dtype="uint8"),
        }
    )

    assert builder._maturity_backstep_count(frame) == 1


def test_sr3_contract_universe_excludes_serial_months() -> None:
    definitions = pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2022-01-01T00:00:00Z"),
                "instrument_id": 1,
                "raw_symbol": "SR3M2",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2022-06-15T16:00:00Z"),
                "maturity_year": 2022,
                "maturity_month": 6,
            },
            {
                "ts_event": pd.Timestamp("2022-01-01T00:00:00Z"),
                "instrument_id": 2,
                "raw_symbol": "SR3K2",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2022-05-15T16:00:00Z"),
                "maturity_year": 2022,
                "maturity_month": 5,
            },
            {
                "ts_event": pd.Timestamp("2022-01-01T00:00:00Z"),
                "instrument_id": 3,
                "raw_symbol": "SR3U2",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2022-09-15T16:00:00Z"),
                "maturity_year": 2022,
                "maturity_month": 9,
            },
        ]
    )
    ohlcv = pd.DataFrame(
        [
            _ohlcv_row("2022-04-01T15:00:00Z", 1, "SR3M2", 95.0),
            _ohlcv_row("2022-07-25T14:02:00Z", 2, "SR3K2", 95.1),
            _ohlcv_row("2022-07-25T14:03:00Z", 3, "SR3U2", 95.2),
        ]
    )

    candidate, metrics = builder.build_front_contract_candidate_frame(
        ohlcv=ohlcv,
        definitions=definitions,
        status=_status_frame(),
        statistics=_statistics_frame(),
        market="SR3",
        year=2022,
        source_files=["candidate.dbn.zst"],
        source_hashes=["a" * 64],
    )

    assert metrics["contract_universe_policy"] == "quarterly_outright_futures"
    assert metrics["outright_ohlcv_rows"] == 3
    assert metrics["contract_universe_ohlcv_rows"] == 2
    assert metrics["dropped_non_contract_universe_rows"] == 1
    assert candidate["raw_symbol"].tolist() == ["SR3M2", "SR3U2"]


def test_deferred_rows_without_point_in_time_definition_are_dropped_before_enrichment() -> None:
    definitions = pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp("2023-12-01T00:00:00Z"),
                "instrument_id": 1,
                "raw_symbol": "SR1H4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2024-03-15T16:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 3,
            },
            {
                "ts_event": pd.Timestamp("2024-02-01T00:00:00Z"),
                "instrument_id": 2,
                "raw_symbol": "SR1M4",
                "instrument_class": "F",
                "min_price_increment": 0.0025,
                "expiration": pd.Timestamp("2024-06-15T16:00:00Z"),
                "maturity_year": 2024,
                "maturity_month": 6,
            },
        ]
    )
    ohlcv = pd.DataFrame(
        [
            _ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.0),
            _ohlcv_row("2024-01-02T15:00:00Z", 2, "SR1M4", 96.0),
        ]
    )

    candidate, metrics = builder.build_front_contract_candidate_frame(
        ohlcv=ohlcv,
        definitions=definitions,
        status=_status_frame(),
        statistics=_statistics_frame(),
        market="SR1",
        year=2024,
        source_files=["candidate.dbn.zst"],
        source_hashes=["a" * 64],
    )

    assert candidate["raw_symbol"].tolist() == ["SR1H4"]
    assert metrics["dropped_deferred_contract_rows"] == 1


def test_parse_excluded_market_years() -> None:
    assert builder._parse_excluded_market_years(["SR3:2018", "SR1:2024"]) == {
        ("SR3", 2018),
        ("SR1", 2024),
    }
    with pytest.raises(ValueError, match="expected MARKET:YEAR"):
        builder._parse_excluded_market_years(["SR3-2018"])


def test_candidate_raw_alignment_manifest_passes_phase2_guard(tmp_path: Path) -> None:
    output_root = tmp_path / "data" / "raw" / "candidates" / "sr_front_contract"
    output_path = output_root / "SR1" / "2024.parquet"
    output_path.parent.mkdir(parents=True)
    pd.DataFrame([_ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.0)]).to_parquet(
        output_path,
        index=False,
    )
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_3:",
                "    markets: [SR1]",
                "    years: [2024]",
            ]
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "reports" / "candidate_alignment.json"

    builder._write_raw_alignment_manifest(
        report_path,
        profile="tier_3",
        resolved_profile="tier_3",
        candidate_dbn_root=tmp_path / "data" / "dbn" / "candidates" / "sr_parent",
        sidecar_dbn_root=tmp_path / "data" / "dbn",
        output_root=output_root,
        rows=[
            {
                "market": "SR1",
                "year": 2024,
                "output_path": output_path.as_posix(),
                "output_hash": "b" * 64,
            }
        ],
        failures=[],
    )

    assert raw_alignment_guard_failures(
        report_path=report_path,
        raw_root=output_root,
        profile="tier_3",
        profile_config_path=config,
    ) == []


def _write_dbn_manifest(
    root: Path,
    *,
    schema_dir: str,
    schema_name: str,
    stype_in: str,
    symbols: list[str],
) -> None:
    folder = root / schema_dir / "SR1" / "2024"
    folder.mkdir(parents=True, exist_ok=True)
    dbn = folder / "2024-01-01_2025-01-01.dbn.zst"
    dbn.write_bytes(schema_dir.encode("utf-8"))
    manifest = {
        "vendor": "databento",
        "dataset": "GLBX.MDP3",
        "schema": schema_name,
        "market": "SR1",
        "symbols_requested": symbols,
        "start": "2024-01-01",
        "end": "2025-01-01",
        "stype_in": stype_in,
        "stype_out": "instrument_id",
        "encoding": "dbn",
        "compression": "zstd",
        "downloaded_at": "2026-06-20T00:00:00+00:00",
        "path": dbn.as_posix(),
        "file_size_bytes": dbn.stat().st_size,
        "file_sha256": hashlib.sha256(dbn.read_bytes()).hexdigest(),
        "job_id": "test",
        "api_client_version": "test",
        "request_status": "ok",
    }
    dbn.with_name(dbn.name + ".manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_candidate_build_source_audit_failure_writes_no_raw_outputs(tmp_path: Path) -> None:
    candidate_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    sidecar_root = tmp_path / "data" / "dbn"
    output_root = tmp_path / "data" / "raw" / "candidates" / "sr_front_contract"
    reports_root = tmp_path / "reports"
    _write_dbn_manifest(
        candidate_root,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="continuous",
        symbols=["SR1.v.0"],
    )
    for schema_dir, schema_name in [
        ("definition", "definition"),
        ("status", "status"),
        ("statistics", "statistics"),
    ]:
        _write_dbn_manifest(
            sidecar_root,
            schema_dir=schema_dir,
            schema_name=schema_name,
            stype_in="parent",
            symbols=["SR1.FUT"],
        )

    report = builder.build_candidate_outputs(
        candidate_dbn_root=candidate_root,
        sidecar_dbn_root=sidecar_root,
        output_root=output_root,
        reports_root=reports_root,
        markets=["SR1"],
        years=[2024],
        profile="tier_3",
        resolved_profile="tier_3_research",
    )

    assert report["status"] == "FAIL"
    assert report["outputs"] == []
    assert not output_root.exists()
    assert (reports_root / builder.MANIFEST_NAME).exists()


class _OptionalFrame:
    def __init__(self, frame: pd.DataFrame, path: Path) -> None:
        self.frame = frame
        self.paths = [path]


def test_candidate_build_fails_alignment_when_sidecar_coverage_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    definition_root = tmp_path / "data" / "dbn"
    status_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    statistics_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    output_root = tmp_path / "data" / "raw" / "candidates" / "sr_front_contract"
    reports_root = tmp_path / "reports"
    source_path = candidate_root / "ohlcv_1m" / "SR1" / "2024" / "chunk.dbn.zst"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"dbn")

    monkeypatch.setattr(
        builder,
        "build_source_audit",
        lambda **_: {
            "status": "PASS",
            "repair_source_ready_count": 1,
            "blocked_count": 0,
        },
    )
    monkeypatch.setattr(builder, "_ohlcv_paths", lambda *_: [source_path])
    monkeypatch.setattr(builder, "file_sha256", lambda _: "a" * 64)
    monkeypatch.setattr(
        builder,
        "_load_ohlcv_frame",
        lambda *_: pd.DataFrame(
            [_ohlcv_row("2024-01-02T15:00:00Z", 1, "SR1H4", 95.0)]
        ),
    )
    monkeypatch.setattr(
        builder,
        "definition_frame_for_group",
        lambda *_: (_definition_frame(), [definition_root / "definition.dbn.zst"]),
    )
    monkeypatch.setattr(
        builder,
        "load_optional_schema_frame_for_group",
        lambda root, schema, *_args, **_kwargs: _OptionalFrame(
            pd.DataFrame(columns=_status_frame().columns)
            if schema == "status"
            else pd.DataFrame(columns=_statistics_frame().columns),
            root / schema / "SR1" / "2024" / "sidecar.dbn.zst",
        ),
    )
    monkeypatch.setattr(
        builder,
        "write_required_dataframe_parquet",
        lambda *_args, **_kwargs: pytest.fail("incomplete candidate should not be written"),
    )

    report = builder.build_candidate_outputs(
        candidate_dbn_root=candidate_root,
        sidecar_dbn_root=definition_root,
        definition_dbn_root=definition_root,
        status_dbn_root=status_root,
        statistics_dbn_root=statistics_root,
        output_root=output_root,
        reports_root=reports_root,
        markets=["SR1"],
        years=[2024],
        profile="tier_3",
        resolved_profile="tier_3_research",
    )

    assert report["status"] == "FAIL"
    assert report["outputs"] == []
    assert report["diagnostics"][0]["status_missing_rows"] == 1
    assert report["diagnostics"][0]["statistics_missing_rows"] == 1
    assert report["diagnostics"][0]["status_missing_by_symbol"] == [
        {"raw_symbol": "SR1H4", "rows": 1}
    ]
    assert any("sidecar enrichment incomplete" in failure for failure in report["failures"])
    assert not output_root.exists()
