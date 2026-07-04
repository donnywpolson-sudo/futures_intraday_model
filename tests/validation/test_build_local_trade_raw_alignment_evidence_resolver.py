from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_raw_alignment_evidence_resolver as raw_resolver
from tests.validation import test_build_local_trade_repaired_root_readiness_diagnostic_plan as diagnostic_fixtures
from tests.validation import test_build_local_trade_upstream_manifest_evidence_resolver as fixtures


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_raw_files(tmp_path: Path, pairs: list[tuple[str, int]]) -> None:
    for market, year in pairs:
        path = tmp_path / "data" / "raw" / market / f"{year}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{market} {year}".encode("utf-8"))


def _raw_metric(market: str, year: int) -> dict[str, object]:
    return {
        "market": market,
        "year": year,
        "path": f"data/raw/{market}/{year}.parquet",
        "rows": 10,
        "bad_ohlc_count": 0,
        "duplicate_ts_count": 0,
        "invalid_ts_count": 0,
        "negative_volume_count": 0,
    }


def _alignment_payload(
    *,
    profile: str,
    resolved_profile: str,
    markets: list[str],
    years: list[int],
    raw_metrics: list[dict[str, object]],
    raw_root: str = "data/raw",
    status: str = "PASS",
) -> dict[str, object]:
    return {
        "stage": "raw_dbn_alignment_audit",
        "status": status,
        "audit_completeness": "full",
        "definition_join_status": "checked",
        "profile": profile,
        "resolved_profile": resolved_profile,
        "raw_root": raw_root,
        "markets": markets,
        "years": years,
        "expected_market_year_count": len(markets) * len(years),
        "raw_market_year_count": len(raw_metrics),
        "missing_raw_count": 0,
        "needs_phase1b_conversion_count": 0,
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "invalid_manifest_count": 0,
        "raw_schema_failure_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_mismatch_count": 0,
        "missing_raw": [],
        "needs_phase1b_conversion": [],
        "raw_only_market_years": [],
        "pre_availability_exemptions": [],
        "raw_file_metrics": raw_metrics,
        "failures": [],
    }


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    diagnostic_fixtures._write_candidate_projection_evidence(tmp_path)
    proposal = fixtures._write_proposal(tmp_path)
    diagnostic_root = tmp_path / "reports" / "pipeline_audit" / "diagnostic_v1"
    placeholder = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    if not placeholder.exists():
        _write_json(placeholder, {"stage": "raw_dbn_alignment_audit", "status": "PASS"})
    return proposal, diagnostic_root


def _build(tmp_path: Path, *, staged: list[str] | None = None) -> dict[str, object]:
    proposal, diagnostic_root = _setup(tmp_path)
    return raw_resolver.build_report(
        repo_root=tmp_path,
        proposal_path=proposal,
        diagnostic_reports_root=diagnostic_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
    )


def test_classifies_matching_per_profile_raw_alignment_reports(tmp_path: Path) -> None:
    _write_raw_files(tmp_path, [("ES", 2025), ("ES", 2026)])
    _write_json(
        tmp_path / "reports" / "pipeline_audit" / "raw_alignment" / "tier_3_holdout_2025_raw_alignment.json",
        _alignment_payload(
            profile="tier_3_holdout",
            resolved_profile="tier_3_holdout",
            markets=["ES"],
            years=[2025],
            raw_metrics=[_raw_metric("ES", 2025)],
        ),
    )
    _write_json(
        tmp_path / "reports" / "pipeline_audit" / "raw_alignment" / "tier_3_forward_2026_raw_alignment.json",
        _alignment_payload(
            profile="tier_3_forward",
            resolved_profile="tier_3_forward",
            markets=["ES"],
            years=[2026],
            raw_metrics=[_raw_metric("ES", 2026)],
        ),
    )

    report = _build(tmp_path)

    assert report["summary"]["status"] == raw_resolver.STATUS_READY
    assert report["summary"]["diagnostic_group_count"] == 2
    assert report["summary"]["matching_group_count"] == 2
    assert report["summary"]["raw_observed_scope_unusable_group_count"] == 0
    assert report["summary"]["generated_report_written"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["raw_alignment_generation_approved"] is False
    assert report["summary"]["readiness_diagnostic_approved"] is False
    assert {
        group["classification"] for group in report["groups"]
    } == {raw_resolver.CLASS_MATCHING_READY}


def test_classifies_raw_observed_but_scope_unusable(tmp_path: Path) -> None:
    _write_raw_files(tmp_path, [("ES", 2025), ("ES", 2026)])
    _write_json(
        tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json",
        _alignment_payload(
            profile="tier_3",
            resolved_profile="tier_3_research",
            markets=["ES"],
            years=[],
            raw_metrics=[_raw_metric("ES", 2025), _raw_metric("ES", 2026)],
        ),
    )

    report = _build(tmp_path)

    assert report["summary"]["status"] == raw_resolver.STATUS_READY
    assert report["summary"]["matching_group_count"] == 0
    assert report["summary"]["raw_observed_scope_unusable_group_count"] == 2
    assert report["summary"]["matching_missing_group_count"] == 0
    assert all(
        group["classification"] == raw_resolver.CLASS_RAW_OBSERVED_SCOPE_UNUSABLE
        for group in report["groups"]
    )
    assert all("--expected-only" in group["proposed_generation_command"]["command"] for group in report["groups"])
    assert all(group["approval_required"] is True for group in report["groups"])


def test_staged_generated_paths_fail_closed(tmp_path: Path) -> None:
    _write_raw_files(tmp_path, [("ES", 2025), ("ES", 2026)])

    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == raw_resolver.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert report["summary"]["generated_artifacts_staged"] is False
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_reports(tmp_path: Path, capsys) -> None:
    _write_raw_files(tmp_path, [("ES", 2025), ("ES", 2026)])
    proposal, diagnostic_root = _setup(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = raw_resolver.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--diagnostic-reports-root",
            str(diagnostic_root),
            "--expected-eligible-market-count",
            "2",
            "--expected-proof-status-market-year-count",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{raw_resolver.STAGE} status={raw_resolver.STATUS_READY}" in output
    assert "diagnostic_groups=2" in output
    assert "generated_outputs=0" in output
    assert not (tmp_path / "reports" / "pipeline_audit" / "local_trade_raw_alignment_repair_v1").exists()
