from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import reconcile_phase2_local_trade_causal_inputs as gate


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
            "summary": {"failed_minutes": 0, "unverified_minutes": 0, "status_counts": {"PASS": len(covered_markets)}},
            "market_years": [
                {
                    "market": market,
                    "year": 2025,
                    "status": "PASS",
                    "failures": [],
                    "classification_counts": {"verified_no_trade_rows_inside_ohlcv_gap": 1},
                    "summary": {"failed_minutes": 0, "unverified_minutes": 0},
                }
                for market in covered_markets
            ],
        },
    )
    return path


def _write_causal_file(
    root: Path,
    *,
    market: str = "CL",
    year: int,
    columns: list[str] | None = None,
) -> None:
    columns = columns or ["ts", "is_synthetic", "synthetic_gap_id", "synthetic_gap_size_minutes"]
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        "ts": pa.array(["2025-06-18T00:00:00Z"]),
        "is_synthetic": pa.array([False]),
        "synthetic_gap_id": pa.array([""]),
        "synthetic_gap_size_minutes": pa.array([0]),
        "close": pa.array([1.0]),
    }
    table = pa.table({column: arrays.get(column, pa.array(["x"])) for column in columns})
    pq.write_table(table, path)


def _write_causal_pair(root: Path, *, market: str = "CL", columns: list[str] | None = None) -> None:
    for year in gate.PROOF_YEARS:
        _write_causal_file(root, market=market, year=year, columns=columns)


def _evaluate(paths: dict[str, Path], local_report: Path, candidate_roots: list[Path]):
    return gate.evaluate_reconciliation(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        local_report_paths=[local_report],
        candidate_roots=candidate_roots,
        expected_count=2,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_ready_when_one_root_has_all_required_causal_inputs(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"
    _write_causal_pair(root)

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["usable_roots"] == ["data/causally_gated_normalized"]
    assert report["summary"]["expected_causal_file_count"] == 2
    assert report["summary"]["parquet_rows_scanned"] is False


def test_missing_causal_inputs_fail_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_MISSING
    assert report["candidate_roots"][0]["missing_file_count"] == 2
    assert any(check["name"] == "usable_causal_root_exists" for check in report["checks"] if check["status"] == "FAIL")


def test_missing_required_schema_fails_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"
    _write_causal_pair(root, columns=["ts", "close"])

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_MISSING
    assert report["candidate_roots"][0]["schema_failure_count"] == 2
    assert "missing required column: is_synthetic" in report["candidate_roots"][0]["schema_failures"][0]["failures"]


def test_multiple_usable_roots_require_human_choice(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    first = tmp_path / "data" / "causally_gated_normalized"
    second = tmp_path / "data" / "candidate_other"
    _write_causal_pair(first)
    _write_causal_pair(second)

    report = _evaluate(paths, _write_local_report(tmp_path), [first, second])

    assert report["summary"]["status"] == gate.STATUS_AMBIGUOUS
    assert report["summary"]["usable_root_count"] == 2
    assert any(
        check["name"] == "usable_causal_root_unambiguous"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_covered_markets_are_excluded_from_required_causal_inputs(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"
    _write_causal_pair(root, market="CL")

    report = _evaluate(paths, _write_local_report(tmp_path, covered_markets=["ES"]), [root])

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["uncovered_markets"] == ["CL"]
    assert {"market": "ES", "year": 2025} not in report["expected_pairs"]
    assert {"market": "ES", "year": 2026} not in report["expected_pairs"]


def test_missing_timestamp_column_fails_closed(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"
    _write_causal_pair(root, columns=["is_synthetic", "close"])

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_MISSING
    assert "missing timestamp column" in report["candidate_roots"][0]["schema_failures"][0]["failures"]
