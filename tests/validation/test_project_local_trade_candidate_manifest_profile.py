from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.pipeline_gates import check_upstream_manifest, file_sha256
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate
from scripts.validation import project_local_trade_candidate_manifest_profile as projection


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source_report(path: str, *, classification: str) -> dict[str, object]:
    return {
        "path": path,
        "sha256": "a" * 64,
        "role": "candidate_recovery_shard"
        if classification == "candidate_derived_review_evidence"
        else "tier1_repaired",
        "root_classification": classification,
        "status": "PASS",
    }


def _proposal_row(market: str, year: int, *, classification: str) -> dict[str, object]:
    causal_root = (
        ledger_gate.CANDIDATE_CAUSAL_ROOT
        if classification == "candidate_derived_review_evidence"
        else ledger_gate.TIER1_CAUSAL_ROOT
    )
    path = f"reports/pipeline_audit/{market}_{year}.json"
    return {
        "market": market,
        "year": year,
        "proposed_proof_status": proposal_gate.PROPOSED_STATUS,
        "proposal_only": True,
        "proof_status_promoted": False,
        "source_report_roles": ["candidate_recovery_shard"],
        "source_classifications": [classification],
        "causal_roots": [causal_root],
        "source_reports": [_source_report(path, classification=classification)],
        "evidence_windows": [
            {
                "report_path": path,
                "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
            }
        ],
    }


def _write_proposal(tmp_path: Path, *, candidate_markets: list[str] | None = None) -> Path:
    markets = candidate_markets or ["NG"]
    rows = [
        _proposal_row("ES", 2025, classification="repaired_tier1_convention_evidence"),
        _proposal_row("ES", 2026, classification="repaired_tier1_convention_evidence"),
        *[
            _proposal_row(market, year, classification="candidate_derived_review_evidence")
            for market in markets
            for year in [2025, 2026]
        ],
    ]
    payload = {
        "summary": {
            "stage": proposal_gate.STAGE,
            "status": proposal_gate.STATUS_READY,
            "decision": proposal_gate.DECISION_REVIEW_ONLY,
            "proposal_row_count": len(rows),
            "uncovered_canonical_market_count": 2,
            "unselected_report_count": 0,
            "excluded_report_count": 0,
            "staged_generated_path_count": 0,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "failure_count": 0,
        },
        "checks": [{"name": "input_ledger_review_ready", "status": "PASS"}],
        "proposal_rows": rows,
        "staged_generated_paths": [],
    }
    path = tmp_path / "reports" / "pipeline_audit" / "proposal.json"
    _write_json(path, payload)
    return path


def _write_profile_config(tmp_path: Path) -> Path:
    path = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_text(
        path,
        """
profiles:
  tier_3_holdout:
    markets: ["ES", "NG"]
    years: [2025]
  tier_3_forward:
    markets: ["ES", "NG"]
    years: [2026]
""".lstrip(),
    )
    return path


def _output_row(tmp_path: Path, market: str, year: int) -> dict[str, object]:
    output_path = tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT / market / f"{year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(f"{market} {year}".encode("utf-8"))
    return {
        "market": market,
        "year": year,
        "input_path": f"data/raw/{market}/{year}.parquet",
        "output_path": output_path.as_posix(),
        "raw_rows": 10,
        "output_rows": 12,
        "synthetic_rows": 2,
        "synthetic_gap_count": 1,
        "max_synthetic_gap_minutes": 3,
        "degraded_bar_rows": 0,
        "degraded_session_rows": 0,
        "roll_boundary_count": 0,
        "roll_window_count": 0,
        "warning_count": 0,
        "warnings": [],
        "failure_count": 0,
        "failures": [],
        "status": "PASS",
    }


def _write_source_manifest(tmp_path: Path, *, markets: list[str] | None = None) -> Path:
    source_markets = markets or ["NG"]
    outputs = [_output_row(tmp_path, market, year) for market in source_markets for year in [2025, 2026]]
    output_hashes = {
        str(row["output_path"]): file_sha256(Path(str(row["output_path"])))
        for row in outputs
    }
    manifest = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": "all_raw",
        "resolved_profile": "all_raw",
        "input_root": "data/raw",
        "output_root": (tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT).as_posix(),
        "reports_root": "reports/pipeline_audit/causal_proof_candidates/local_trade_2025_2026_v1",
        "markets": source_markets,
        "years": [2025, 2026],
        "warning_count": 0,
        "failure_count": 0,
        "warnings": [],
        "failures": [],
        "summary": {"file_count": len(outputs), "pass_count": len(outputs), "warn_count": 0, "fail_count": 0},
        "input_file_hashes": {},
        "output_file_hashes": output_hashes,
        "outputs": outputs,
    }
    path = (
        tmp_path
        / "reports"
        / "pipeline_audit"
        / "causal_proof_candidates"
        / "local_trade_2025_2026_v1"
        / "causal_base_manifest.json"
    )
    _write_json(path, manifest)
    return path


def _build(
    tmp_path: Path,
    *,
    staged: list[str] | None = None,
    approved_markets: list[str] | None = None,
    candidate_markets: list[str] | None = None,
    reports_root: Path | None = None,
) -> dict[str, object]:
    _write_profile_config(tmp_path)
    markets = candidate_markets or ["NG"]
    return projection.build_report(
        repo_root=tmp_path,
        proposal_path=_write_proposal(tmp_path, candidate_markets=markets),
        source_manifest_path=_write_source_manifest(tmp_path, markets=markets),
        reports_root=reports_root,
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        approved_markets=approved_markets or ["NG"],
        approved_years=[2025, 2026],
        profile_config=tmp_path / "configs" / "alpha_tiered.yaml",
    )


def test_builds_approved_candidate_projection_without_accepting_repaired_rows(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == projection.STATUS_PROJECTED
    assert report["summary"]["candidate_projection_approved"] is True
    assert report["summary"]["candidate_projection_market_year_count"] == 2
    assert report["summary"]["candidate_projection_manifest_count"] == 2
    assert report["summary"]["repaired_root_market_year_count"] == 2
    assert report["summary"]["repaired_root_warnings_accepted"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["accepted_warning_packet_approved"] is False
    assert report["summary"]["label_build_approved"] is False
    assert all(item["manifest"]["profile"] in {"tier_3_holdout", "tier_3_forward"} for item in report["projected_manifests"])


def test_writes_per_year_causal_base_manifests_that_pass_upstream_gate(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports" / "pipeline_audit" / "projection"
    report = _build(tmp_path, reports_root=reports_root)

    projection.write_projected_manifests(report, repo_root=tmp_path, reports_root=reports_root)

    holdout_manifest = reports_root / "tier_3_holdout_2025" / "causal_base_manifest.json"
    forward_manifest = reports_root / "tier_3_forward_2026" / "causal_base_manifest.json"
    assert holdout_manifest.exists()
    assert forward_manifest.exists()
    holdout_check = check_upstream_manifest(
        manifest_path=holdout_manifest,
        expected_stage="causal_base",
        expected_profile="tier_3_holdout",
        expected_resolved_profile="tier_3_holdout",
        expected_output_root=tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT,
        expected_market_years=[("NG", 2025)],
        gate_name="test_projection_holdout",
    )
    forward_check = check_upstream_manifest(
        manifest_path=forward_manifest,
        expected_stage="causal_base",
        expected_profile="tier_3_forward",
        expected_resolved_profile="tier_3_forward",
        expected_output_root=tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT,
        expected_market_years=[("NG", 2026)],
        gate_name="test_projection_forward",
    )
    assert holdout_check.passed
    assert forward_check.passed
    assert (reports_root / "tier_3_holdout_2025" / "causal_base_manifest.md").exists()


def test_scope_mismatch_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, approved_markets=["HO", "NG"], candidate_markets=["NG"])

    assert report["summary"]["status"] == projection.STATUS_NO_GO
    assert report["summary"]["candidate_projection_approved"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert any(
        check["name"] == "candidate_scope_matches_human_approval"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == projection.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_output_root_outside_reports_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, reports_root=tmp_path / "reports" / "projection")

    with pytest.raises(ValueError, match="reports root must be under reports"):
        projection.write_projected_manifests(
            report,
            repo_root=tmp_path,
            reports_root=tmp_path / "projection",
        )


def test_cli_writes_projected_manifests(tmp_path: Path, capsys) -> None:
    _write_profile_config(tmp_path)
    proposal = _write_proposal(tmp_path)
    source_manifest = _write_source_manifest(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "projection"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = projection.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--source-manifest",
            str(source_manifest),
            "--reports-root",
            str(reports_root),
            "--approved-markets",
            "NG",
            "--approved-years",
            "2025,2026",
            "--profile-config",
            str(tmp_path / "configs" / "alpha_tiered.yaml"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{projection.STAGE} status={projection.STATUS_PROJECTED}" in output
    assert "generated_outputs=4" in output
    assert (reports_root / "tier_3_holdout_2025" / "causal_base_manifest.json").exists()
