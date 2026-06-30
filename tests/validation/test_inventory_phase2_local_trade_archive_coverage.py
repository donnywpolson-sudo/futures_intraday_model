from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import inventory_phase2_local_trade_archive_coverage as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_phase2_fixture(tmp_path: Path) -> dict[str, Path]:
    pairs = [("ES", 2020), ("CL", 2021)]
    data_manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    canonical_root = tmp_path / scope_gate.CANONICAL_ROOT_REL
    reports_root = tmp_path / scope_gate.REPORTS_ROOT_REL
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    build_script = tmp_path / "scripts" / "phase2_causal_base" / "build_causal_base_data.py"
    _write_text(
        data_manifest_path,
        "\n".join(["canonical_paths:", f"  causal_parquet_pattern: {scope_gate.TARGET_CANONICAL_PATTERN}"]),
    )
    _write_text(profile_config, "default_profile: tier_3_research\n")
    _write_text(build_script, "print('builder')\n")

    input_hashes: dict[str, str] = {}
    output_hashes: dict[str, str] = {}
    outputs: list[dict[str, object]] = []
    for market, year in pairs:
        input_rel = f"data/raw/{market}/{year}.parquet"
        output_rel = f"{scope_gate.CANONICAL_ROOT_REL}/{market}/{year}.parquet"
        input_path = tmp_path / input_rel
        output_path = tmp_path / output_rel
        _write_text(input_path, f"input {market} {year}\n")
        _write_text(output_path, f"output {market} {year}\n")
        input_hashes[input_rel] = scope_gate.sha256_file(input_path)
        output_hashes[output_rel] = scope_gate.sha256_file(output_path)
        outputs.append(
            {
                "market": market,
                "year": year,
                "input_path": input_rel,
                "output_path": output_rel,
            }
        )

    _write_json(
        reports_root / "causal_base_manifest.json",
        {
            "status": "PASS",
            "generated_at": "2026-06-30T00:00:00Z",
            "git_commit": "current-head",
            "script_path": "scripts/phase2_causal_base/build_causal_base_data.py",
            "script_hash": scope_gate.sha256_file(build_script),
            "config_hash": scope_gate.sha256_file(profile_config),
            "input_root": "data/raw",
            "output_root": scope_gate.CANONICAL_ROOT_REL,
            "reports_root": scope_gate.REPORTS_ROOT_REL,
            "input_file_hashes": input_hashes,
            "output_file_hashes": output_hashes,
            "market_year_include_count": len(pairs),
            "requested_market_years": [{"market": market, "year": year} for market, year in pairs],
            "outputs": outputs,
        },
    )
    _write_json(
        reports_root / "causal_base_validation.json",
        {
            "status": "PASS",
            "files": [{"market": market, "year": year} for market, year in pairs],
            "summary": {
                "file_count": len(pairs),
                "pass_count": len(pairs),
                "fail_count": 0,
                "local_trade_ohlcv_gap_gate_status": "NOT_RUN",
            },
        },
    )
    return {
        "repo_root": tmp_path,
        "dbn_root": tmp_path / "data" / "dbn",
        "data_manifest_path": data_manifest_path,
        "canonical_root": canonical_root,
        "reports_root": reports_root,
        "phase2_manifest_path": reports_root / "causal_base_manifest.json",
        "phase2_validation_path": reports_root / "causal_base_validation.json",
        "profile_config_path": profile_config,
        "build_script_path": build_script,
    }


def _write_local_report(tmp_path: Path, *, covered_markets: list[str] | None = None) -> Path:
    covered_markets = covered_markets or ["ES"]
    market_years = [
        {
            "market": market,
            "year": 2025,
            "status": "PASS",
            "failures": [],
            "classification_counts": {"verified_no_trade_rows_inside_ohlcv_gap": 1},
            "summary": {"failed_minutes": 0, "unverified_minutes": 0},
        }
        for market in covered_markets
    ]
    path = tmp_path / "reports" / "pipeline_audit" / "local_trade_ohlcv_gap_crosscheck.json"
    _write_json(
        path,
        {
            "generated_at_utc": "2026-06-19T00:00:00+00:00",
            "status": "PASS",
            "failures": [],
            "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
            "caveat": "This is not direct trades proof outside the access window.",
            "window": gate.proof_gate.EXPECTED_ACCESS_WINDOW,
            "local_trades_schema_access": gate.proof_gate.EXPECTED_ACCESS_WINDOW,
            "dbn_root": "data/dbn",
            "raw_root": "data/raw",
            "causal_root": "data/causally_gated_normalized",
            "summary": {"failed_minutes": 0, "unverified_minutes": 0, "status_counts": {"PASS": len(market_years)}},
            "market_years": market_years,
        },
    )
    return path


def _manifest(path: Path, *, repo_root: Path, schema: str, market: str, start: str, end: str) -> dict[str, object]:
    rel_path = path.relative_to(repo_root).as_posix()
    return {
        "vendor": "databento",
        "dataset": "GLBX.MDP3",
        "schema": schema,
        "market": market,
        "symbols_requested": [f"{market}.v.0"],
        "start": start,
        "end": end,
        "stype_in": "parent" if schema == "definition" else "continuous",
        "stype_out": "instrument_id",
        "encoding": "dbn",
        "compression": "zstd",
        "downloaded_at": "2026-06-19T00:00:00+00:00",
        "path": rel_path,
        "file_size_bytes": path.stat().st_size,
        "file_sha256": "manifest-hash-not-recomputed-by-inventory",
        "job_id": "job-test",
        "api_client_version": "test",
        "request_status": "ok",
    }


def _write_archive(
    dbn_root: Path,
    *,
    repo_root: Path,
    schema: str,
    market: str = "CL",
    year: int = 2025,
    start: str = "2025-06-18",
    end: str = "2026-01-01",
    manifest_schema: str | None = None,
) -> Path:
    path = dbn_root / gate.SCHEMA_PATHS[schema] / market / str(year) / f"{start}_{end}.dbn.zst"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a valid dbn payload")
    payload = _manifest(
        path,
        repo_root=repo_root,
        schema=manifest_schema or schema,
        market=market,
        start=start,
        end=end,
    )
    _write_json(path.with_name(f"{path.name}.manifest.json"), payload)
    return path


def _write_complete_archives(dbn_root: Path, *, repo_root: Path, market: str = "CL") -> None:
    for schema in gate.SCHEMAS_TO_INVENTORY:
        _write_archive(
            dbn_root,
            repo_root=repo_root,
            schema=schema,
            market=market,
            year=2025,
            start="2025-06-18",
            end="2026-01-01",
        )
        _write_archive(
            dbn_root,
            repo_root=repo_root,
            schema=schema,
            market=market,
            year=2026,
            start="2026-01-01",
            end="2026-06-13",
        )


def _evaluate(paths: dict[str, Path], local_report: Path):
    return gate.evaluate_inventory(
        repo_root=paths["repo_root"],
        dbn_root=paths["dbn_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        local_report_paths=[local_report],
        expected_count=2,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_ready_when_uncovered_markets_have_complete_manifest_coverage(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    _write_complete_archives(paths["dbn_root"], repo_root=paths["repo_root"])

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["uncovered_markets"] == ["CL"]
    assert report["covered_markets"] == ["ES"]
    assert report["summary"]["dbn_payload_rows_scanned"] is False


def test_missing_trades_directory_fails_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    for schema in ("ohlcv-1m", "definition"):
        _write_archive(paths["dbn_root"], repo_root=paths["repo_root"], schema=schema)

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any("CL trades: missing market directory" in item for item in report["checks"][1]["observed"])


def test_wrong_manifest_schema_fails_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    _write_complete_archives(paths["dbn_root"], repo_root=paths["repo_root"])
    _write_archive(
        paths["dbn_root"],
        repo_root=paths["repo_root"],
        schema="trades",
        year=2025,
        start="2025-06-18",
        end="2026-01-01",
        manifest_schema="mbp-1",
    )

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any("manifest schema mismatch" in item for item in report["checks"][1]["observed"])


def test_partial_interval_coverage_fails_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    for schema in gate.SCHEMAS_TO_INVENTORY:
        _write_archive(
            paths["dbn_root"],
            repo_root=paths["repo_root"],
            schema=schema,
            year=2025,
            start="2025-06-18",
            end="2025-12-01",
        )

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any("uncovered requested window" in item for item in report["checks"][1]["observed"])


def test_covered_markets_are_excluded_from_inventory(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    _write_complete_archives(paths["dbn_root"], repo_root=paths["repo_root"], market="CL")

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_READY
    assert "ES" not in report["by_market"]
    assert "CL" in report["by_market"]


def test_invalid_dbn_payload_is_not_decoded_when_manifest_metadata_is_valid(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    _write_complete_archives(paths["dbn_root"], repo_root=paths["repo_root"], market="CL")

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["dbn_payload_rows_scanned"] is False
