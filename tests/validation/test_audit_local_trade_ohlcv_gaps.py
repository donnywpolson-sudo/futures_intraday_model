from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

from scripts.phase1A_download.download_databento_raw import (
    CME_DATASET,
    DownloadTask,
    build_raw_file_manifest,
    symbol_for_product,
)
from scripts.phase1_raw_contract import SCHEMA_PATHS
from scripts.validation.audit_local_trade_ohlcv_gaps import (
    TRADE_ACTIVITY,
    UNVERIFIED_CONTRACT,
    VERIFIED_NO_TRADE,
    build_report,
)


def _write_config(path: Path, markets: list[str]) -> None:
    payload = {
        "profiles": {
            "tier_3_holdout": {"markets": markets, "years": [2025]},
            "tier_3_forward": {"markets": markets, "years": [2026]},
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_archive(
    root: Path,
    *,
    schema: str,
    market: str = "ES",
    start: str = "2025-06-18",
    end: str = "2025-06-19",
    manifest_schema: str | None = None,
) -> Path:
    year = int(start[:4])
    archive = root / SCHEMA_PATHS[schema] / market / str(year) / f"{start}_{end}.dbn.zst"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"dbn")
    stype_in = "parent" if schema == "definition" else "continuous"
    task = DownloadTask(
        dataset=CME_DATASET,
        product=market,
        year=year,
        start=start,
        end=end,
        symbol=symbol_for_product(market, stype_in),
        output_path=archive.as_posix(),
        schema=schema,
        stype_in=stype_in,
        stype_out="instrument_id",
        chunk="year",
        raw_format="dbn-zstd",
    )
    manifest = build_raw_file_manifest(task, archive, job_id="job-test", request_status="ok")
    if manifest_schema is not None:
        manifest["schema"] = manifest_schema
    archive.with_name(f"{archive.name}.manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return archive


def _write_all_archives(root: Path, market: str = "ES") -> None:
    for schema in ("ohlcv-1m", "definition", "trades"):
        _write_archive(root, schema=schema, market=market)


def _write_raw_causal(
    root: Path,
    *,
    market: str = "ES",
    raw_instruments: tuple[int, int] = (100, 100),
    synthetic: bool = True,
) -> None:
    raw = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2025-06-18T00:00:00Z", "2025-06-18T00:02:00Z"],
                utc=True,
            ),
            "instrument_id": list(raw_instruments),
            "raw_symbol": ["ESU5", "ESU5"],
            "source_file": ["raw.dbn.zst", "raw.dbn.zst"],
            "source_sha256": ["abc", "abc"],
        }
    )
    causal_rows = [
        {
            "ts": pd.Timestamp("2025-06-18T00:00:00Z"),
            "instrument_id": raw_instruments[0],
            "raw_symbol": "ESU5",
            "is_synthetic": False,
        },
        {
            "ts": pd.Timestamp("2025-06-18T00:02:00Z"),
            "instrument_id": raw_instruments[1],
            "raw_symbol": "ESU5",
            "is_synthetic": False,
        },
    ]
    if synthetic:
        causal_rows.insert(
            1,
            {
                "ts": pd.Timestamp("2025-06-18T00:01:00Z"),
                "instrument_id": raw_instruments[0],
                "raw_symbol": "ESU5",
                "is_synthetic": True,
                "synthetic_gap_id": "gap-1",
                "synthetic_gap_size_minutes": 1,
            },
        )
    causal = pd.DataFrame(causal_rows)
    raw_path = root / "data" / "raw" / market / "2025.parquet"
    causal_path = root / "data" / "causally_gated_normalized" / market / "2025.parquet"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    causal_path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(raw_path, index=False)
    causal.to_parquet(causal_path, index=False)


def _args(root: Path, *, inventory_only: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        profile_config=str(root / "configs" / "alpha_tiered.yaml"),
        profiles=["tier_3_holdout"],
        markets=None,
        start="2025-06-18",
        end="2025-06-19",
        dbn_root=str(root / "data" / "dbn"),
        raw_root=str(root / "data" / "raw"),
        causal_root=str(root / "data" / "causally_gated_normalized"),
        json_out=str(root / "reports" / "audit.json"),
        md_out=str(root / "reports" / "audit.md"),
        chunk_size=2,
        max_gap_windows=None,
        inventory_only=inventory_only,
    )


class FakeTradeReader:
    def __init__(self, frames: list[pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[tuple[Path, int]] = []

    def __call__(self, path: Path, chunk_size: int) -> Iterable[pd.DataFrame]:
        self.calls.append((path, chunk_size))
        yield from self.frames


def _trade_frame(ts_values: list[str], instrument_ids: list[int] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_event": pd.to_datetime(ts_values, utc=True),
            "instrument_id": instrument_ids or [100] * len(ts_values),
            "price": [100.0] * len(ts_values),
            "size": [1] * len(ts_values),
        }
    )


def test_missing_trade_market_fails_closed(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_archive(tmp_path / "data" / "dbn", schema="ohlcv-1m")
    _write_archive(tmp_path / "data" / "dbn", schema="definition")

    report = build_report(_args(tmp_path, inventory_only=True), trade_frame_reader=FakeTradeReader([]))

    assert report["status"] == "FAIL"
    assert any("ES trades: missing market directory" in item for item in report["failures"])


def test_invalid_trade_manifest_fails_closed(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_archive(tmp_path / "data" / "dbn", schema="ohlcv-1m")
    _write_archive(tmp_path / "data" / "dbn", schema="definition")
    _write_archive(tmp_path / "data" / "dbn", schema="trades", manifest_schema="mbp-1")

    report = build_report(_args(tmp_path, inventory_only=True), trade_frame_reader=FakeTradeReader([]))

    assert report["status"] == "FAIL"
    assert any("manifest schema mismatch" in item for item in report["failures"])


def test_no_synthetic_gaps_passes_with_valid_coverage(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_all_archives(tmp_path / "data" / "dbn")
    _write_raw_causal(tmp_path, synthetic=False)
    reader = FakeTradeReader([])

    report = build_report(_args(tmp_path), trade_frame_reader=reader)

    assert report["status"] == "PASS"
    assert report["summary"]["missing_minute_count"] == 0
    assert reader.calls == []


def test_synthetic_gap_without_trade_rows_passes_gap(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_all_archives(tmp_path / "data" / "dbn")
    _write_raw_causal(tmp_path)
    reader = FakeTradeReader([_trade_frame(["2025-06-18T00:00:30Z", "2025-06-18T00:02:30Z"])])

    report = build_report(_args(tmp_path), trade_frame_reader=reader)
    gap = report["market_years"][0]["gap_windows"][0]

    assert report["status"] == "PASS"
    assert gap["classification"] == VERIFIED_NO_TRADE
    assert gap["trade_rows_inside_ohlcv_gap"] == 0


def test_synthetic_gap_with_trade_row_fails_gap(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_all_archives(tmp_path / "data" / "dbn")
    _write_raw_causal(tmp_path)
    reader = FakeTradeReader([_trade_frame(["2025-06-18T00:01:30Z"])])

    report = build_report(_args(tmp_path), trade_frame_reader=reader)
    gap = report["market_years"][0]["gap_windows"][0]

    assert report["status"] == "FAIL"
    assert gap["classification"] == TRADE_ACTIVITY
    assert gap["trade_rows_inside_ohlcv_gap"] == 1


def test_unresolved_adjacent_contract_fails_closed(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_all_archives(tmp_path / "data" / "dbn")
    _write_raw_causal(tmp_path, raw_instruments=(100, 200))

    report = build_report(_args(tmp_path), trade_frame_reader=FakeTradeReader([]))
    gap = report["market_years"][0]["gap_windows"][0]

    assert report["status"] == "FAIL"
    assert gap["classification"] == UNVERIFIED_CONTRACT
    assert "adjacent contract context unresolved" in gap["failures"]


def test_chunked_trade_frames_are_aggregated(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml", ["ES"])
    _write_all_archives(tmp_path / "data" / "dbn")
    _write_raw_causal(tmp_path)
    reader = FakeTradeReader(
        [
            _trade_frame(["2025-06-18T00:00:30Z"]),
            _trade_frame(["2025-06-18T00:01:15Z"]),
        ]
    )

    report = build_report(_args(tmp_path), trade_frame_reader=reader)
    gap = report["market_years"][0]["gap_windows"][0]

    assert reader.calls[0][1] == 2
    assert report["summary"]["trade_rows_scanned"] == 2
    assert gap["classification"] == TRADE_ACTIVITY
    assert gap["trade_rows_inside_ohlcv_gap"] == 1
