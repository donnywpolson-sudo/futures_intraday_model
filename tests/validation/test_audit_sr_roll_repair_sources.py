from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.validation import audit_sr_roll_repair_sources as audit


def _write_dbn_with_manifest(
    root: Path,
    *,
    schema_dir: str,
    schema_name: str,
    market: str = "SR1",
    year: int = 2024,
    stype_in: str = "parent",
    symbols: list[str] | None = None,
) -> Path:
    symbols = symbols or [f"{market}.FUT"]
    folder = root / schema_dir / market / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    dbn = folder / f"{year}-01-01_{year + 1}-01-01.dbn.zst"
    dbn.write_bytes(f"{schema_dir}-{market}-{year}".encode("utf-8"))
    manifest = {
        "vendor": "databento",
        "schema": schema_name,
        "market": market,
        "symbols_requested": symbols,
        "start": f"{year}-01-01",
        "end": f"{year + 1}-01-01",
        "stype_in": stype_in,
        "stype_out": "instrument_id",
        "request_status": "ok",
        "file_sha256": hashlib.sha256(dbn.read_bytes()).hexdigest(),
    }
    manifest_path = dbn.with_name(dbn.name + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _write_complete_sidecars(
    root: Path,
    *,
    market: str = "SR1",
    year: int = 2024,
    stype_in: str = "parent",
    symbols: list[str] | None = None,
) -> None:
    symbols = symbols or [f"{market}.FUT"]
    _write_dbn_with_manifest(
        root,
        schema_dir="definition",
        schema_name="definition",
        market=market,
        year=year,
        stype_in=stype_in,
        symbols=symbols,
    )
    _write_dbn_with_manifest(
        root,
        schema_dir="status",
        schema_name="status",
        market=market,
        year=year,
        stype_in=stype_in,
        symbols=symbols,
    )
    _write_dbn_with_manifest(
        root,
        schema_dir="statistics",
        schema_name="statistics",
        market=market,
        year=year,
        stype_in=stype_in,
        symbols=symbols,
    )


def test_continuous_ohlcv_source_blocks_explicit_roll_repair(tmp_path: Path) -> None:
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="continuous",
        symbols=["SR1.v.0"],
    )
    _write_complete_sidecars(tmp_path)

    row = audit.audit_market_year(tmp_path, "SR1", 2024)

    assert row["status"] == "FAIL"
    assert row["repair_source_ready"] is False
    assert any("continuous-only" in blocker for blocker in row["blockers"])


def test_parent_ohlcv_with_required_sidecars_passes(tmp_path: Path) -> None:
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="parent",
        symbols=["SR1.FUT"],
    )
    _write_complete_sidecars(tmp_path)

    report = audit.build_report(dbn_root=tmp_path, markets=["SR1"], years=[2024])

    assert report["status"] == "PASS"
    assert report["repair_source_ready_count"] == 1
    assert report["blocked_count"] == 0


def test_parent_ohlcv_with_continuous_sidecars_blocks_repair_source(tmp_path: Path) -> None:
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="parent",
        symbols=["SR1.FUT"],
    )
    _write_complete_sidecars(
        tmp_path,
        stype_in="continuous",
        symbols=["SR1.v.0"],
    )

    row = audit.audit_market_year(tmp_path, "SR1", 2024)

    assert row["status"] == "FAIL"
    assert any("status DBN is continuous-only" in blocker for blocker in row["blockers"])
    assert any("statistics DBN is continuous-only" in blocker for blocker in row["blockers"])


def test_parent_ohlcv_candidate_root_can_use_canonical_sidecar_root(tmp_path: Path) -> None:
    ohlcv_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    sidecar_root = tmp_path / "data" / "dbn"
    _write_dbn_with_manifest(
        ohlcv_root,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="parent",
        symbols=["SR1.FUT"],
    )
    _write_complete_sidecars(sidecar_root)

    report = audit.build_report(
        dbn_root=ohlcv_root,
        definition_dbn_root=sidecar_root,
        status_dbn_root=sidecar_root,
        statistics_dbn_root=sidecar_root,
        markets=["SR1"],
        years=[2024],
    )

    assert report["status"] == "PASS"
    assert report["dbn_root"] == ohlcv_root.as_posix()
    assert report["definition_dbn_root"] == sidecar_root.as_posix()
    assert report["status_dbn_root"] == sidecar_root.as_posix()
    assert report["statistics_dbn_root"] == sidecar_root.as_posix()


def test_parent_ohlcv_schema_root_layout_passes(tmp_path: Path) -> None:
    ohlcv_root = tmp_path / "data" / "dbn" / "candidates" / "sr_parent"
    sidecar_root = tmp_path / "data" / "dbn"
    _write_dbn_with_manifest(
        ohlcv_root,
        schema_dir="",
        schema_name="ohlcv-1m",
        stype_in="parent",
        symbols=["SR1.FUT"],
    )
    _write_complete_sidecars(sidecar_root)

    report = audit.build_report(
        dbn_root=ohlcv_root,
        sidecar_dbn_root=sidecar_root,
        markets=["SR1"],
        years=[2024],
    )

    assert report["status"] == "PASS"


def test_missing_definition_sidecar_blocks_repair_source(tmp_path: Path) -> None:
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="parent",
        symbols=["SR1.FUT"],
    )
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="status",
        schema_name="status",
    )
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="statistics",
        schema_name="statistics",
    )

    row = audit.audit_market_year(tmp_path, "SR1", 2024)

    assert row["status"] == "FAIL"
    assert "missing definition DBN manifest" in row["blockers"]


def test_cli_writes_json_only_when_requested(tmp_path: Path, capsys) -> None:
    _write_dbn_with_manifest(
        tmp_path,
        schema_dir="ohlcv_1m",
        schema_name="ohlcv-1m",
        stype_in="continuous",
        symbols=["SR1.v.0"],
    )
    _write_complete_sidecars(tmp_path)
    json_out = tmp_path / "reports" / "audit.json"

    result = audit.main(
        [
            "--dbn-root",
            str(tmp_path),
            "--markets",
            "SR1",
            "--years",
            "2024",
        ]
    )
    assert result == 1
    assert not json_out.exists()

    result = audit.main(
        [
            "--dbn-root",
            str(tmp_path),
            "--markets",
            "SR1",
            "--years",
            "2024",
            "--json-out",
            str(json_out),
        ]
    )
    assert result == 1
    assert json_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "FAIL"
    assert "FAIL SR roll repair source audit" in capsys.readouterr().out
