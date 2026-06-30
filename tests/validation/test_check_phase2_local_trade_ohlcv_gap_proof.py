from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import check_phase2_460_audit_readiness as scope_gate
from scripts.validation import check_phase2_local_trade_ohlcv_gap_proof as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_phase2_fixture(
    tmp_path: Path,
    *,
    pairs: list[tuple[str, int]] | None = None,
) -> dict[str, Path]:
    pairs = pairs or [("ES", 2020), ("CL", 2021)]
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


def _write_local_report(
    tmp_path: Path,
    *,
    markets: list[str] | None = None,
    status: str = "PASS",
    caveat: str | None = None,
    failed_minutes: int = 0,
    unverified_minutes: int = 0,
) -> Path:
    markets = markets or ["ES", "CL"]
    caveat = caveat if caveat is not None else "This is not direct trades proof outside the access window."
    market_years = [
        {
            "market": market,
            "year": 2025,
            "status": "PASS" if failed_minutes == 0 and unverified_minutes == 0 else "FAIL",
            "failures": [],
            "classification_counts": {
                "verified_no_trade_rows_inside_ohlcv_gap": 1,
            },
            "summary": {
                "failed_minutes": failed_minutes,
                "unverified_minutes": unverified_minutes,
            },
        }
        for market in markets
    ]
    report = {
        "generated_at_utc": "2026-06-19T00:00:00+00:00",
        "status": status,
        "failures": [] if status == "PASS" else ["local trade evidence failed"],
        "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
        "caveat": caveat,
        "window": gate.EXPECTED_ACCESS_WINDOW,
        "local_trades_schema_access": gate.EXPECTED_ACCESS_WINDOW,
        "dbn_root": "data/dbn",
        "raw_root": "data/raw",
        "causal_root": "data/causally_gated_normalized",
        "summary": {
            "failed_minutes": failed_minutes,
            "unverified_minutes": unverified_minutes,
            "status_counts": {"PASS": len(markets)},
        },
        "market_years": market_years,
    }
    path = tmp_path / "reports" / "pipeline_audit" / "local_trade_ohlcv_gap_crosscheck.json"
    _write_json(path, report)
    return path


def _evaluate(paths: dict[str, Path], local_report: Path, *, expected_count: int = 2):
    return gate.evaluate_gap_proof(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        local_report_paths=[local_report],
        expected_count=expected_count,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_passes_when_convention_evidence_covers_all_canonical_markets(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    report = _evaluate(paths, _write_local_report(tmp_path))

    assert report["summary"]["status"] == gate.STATUS_GO
    assert report["summary"]["direct_historical_trade_proof_claimed"] is False
    assert report["summary"]["convention_backed_only"] is True
    assert report["summary"]["missing_market_count"] == 0
    assert report["warnings"][0]["code"] == gate.WARN_CONVENTION_ONLY


def test_fails_when_scope_gate_fails(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path, pairs=[("ES", 2020), ("6M", 2012), ("CL", 2025)])
    report = _evaluate(paths, _write_local_report(tmp_path, markets=["ES", "6M", "CL"]), expected_count=3)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "manifest_trust_gate_passed"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_manifest_trust_gate_fails(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    _write_text(paths["repo_root"] / "data/raw/ES/2020.parquet", "changed input\n")

    report = _evaluate(paths, _write_local_report(tmp_path))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "manifest_trust_gate_passed"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_local_trade_report_status_is_not_pass(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    report = _evaluate(paths, _write_local_report(tmp_path, status="FAIL"))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "local_trade_reports_status_pass"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_report_does_not_cover_all_canonical_markets(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    report = _evaluate(paths, _write_local_report(tmp_path, markets=["ES"]))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["missing_markets"] == ["CL"]
    assert any(
        check["name"] == "canonical_markets_covered_by_convention_evidence"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_report_lacks_non_direct_proof_caveat(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    report = _evaluate(paths, _write_local_report(tmp_path, caveat="Direct proof approved."))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "local_trade_caveat_preserves_non_direct_proof"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_report_has_failed_or_unverified_minutes(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    report = _evaluate(paths, _write_local_report(tmp_path, failed_minutes=1, unverified_minutes=1))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "local_trade_reports_no_failed_unverified_minutes"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
    assert any(
        check["name"] == "local_trade_report_entries_pass"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )
