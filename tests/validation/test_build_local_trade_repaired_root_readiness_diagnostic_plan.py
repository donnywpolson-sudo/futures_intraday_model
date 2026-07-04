from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_repaired_root_readiness_diagnostic_plan as diagnostic_plan
from scripts.validation import build_local_trade_upstream_manifest_evidence_resolver as resolver
from tests.validation import test_build_local_trade_upstream_manifest_evidence_resolver as fixtures


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_raw_alignment_placeholder(tmp_path: Path) -> Path:
    path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_json(path, {"status": "PASS"})
    return path


def _write_raw_alignment_override(tmp_path: Path, profile: str, year: int) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "raw_alignment" / f"{profile}_{year}.json"
    _write_json(path, {"status": "PASS", "profile": profile, "year": year})
    return path


def _write_projected_candidate_manifest(tmp_path: Path, *, profile: str, year: int) -> None:
    output_path = tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT / "NG" / f"{year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(f"NG {year}".encode("utf-8"))
    manifest = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": profile,
        "resolved_profile": profile,
        "output_root": (tmp_path / ledger_gate.CANDIDATE_CAUSAL_ROOT).as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "warnings": [],
        "failures": [],
        "summary": {"warn_count": 0, "fail_count": 0},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "NG",
                "year": year,
                "status": "PASS",
                "warning_count": 0,
                "failure_count": 0,
                "warnings": [],
                "failures": [],
            }
        ],
    }
    _write_json(
        tmp_path / "reports" / "pipeline_audit" / "projected_candidate" / f"{profile}_{year}" / "causal_base_manifest.json",
        manifest,
    )


def _write_candidate_projection_evidence(tmp_path: Path) -> None:
    _write_projected_candidate_manifest(tmp_path, profile="tier_3_holdout", year=2025)
    _write_projected_candidate_manifest(tmp_path, profile="tier_3_forward", year=2026)


def _build(tmp_path: Path, *, staged: list[str] | None = None, projected: bool = True) -> dict[str, object]:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    if projected:
        _write_candidate_projection_evidence(tmp_path)
    raw_alignment = _write_raw_alignment_placeholder(tmp_path)
    return diagnostic_plan.build_report(
        repo_root=tmp_path,
        proposal_path=fixtures._write_proposal(tmp_path),
        diagnostic_reports_root=tmp_path / "reports" / "pipeline_audit" / "diagnostic_v1",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
    )


def test_builds_console_only_repaired_root_readiness_diagnostic_plan(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == diagnostic_plan.STATUS_READY
    assert report["summary"]["input_resolver_status"] == resolver.STATUS_PLAN_READY
    assert report["summary"]["diagnostic_group_count"] == 2
    assert report["summary"]["diagnostic_market_year_count"] == 2
    assert report["summary"]["candidate_projection_blocker_count"] == 0
    assert report["summary"]["repaired_warning_group_count"] == 2
    assert report["summary"]["selected_warning_row_count"] == 2
    assert report["summary"]["generated_report_written"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["readiness_diagnostic_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["label_build_approved"] is False

    commands = [group["command"] for group in report["diagnostic_groups"]]
    assert all("--readiness-only" in command for command in commands)
    assert all("--market-year-include-list" in command for command in commands)
    assert all("--readiness-max-market-years 1" in command for command in commands)
    assert any("--profile tier_3_holdout" in command for command in commands)
    assert any("--profile tier_3_forward" in command for command in commands)
    include_payloads = [group["include_list_payload"] for group in report["diagnostic_groups"]]
    assert {row["year"] for payload in include_payloads for row in payload["market_years"]} == {2025, 2026}
    assert {row["market"] for payload in include_payloads for row in payload["market_years"]} == {"ES"}


def test_supports_per_group_raw_alignment_report_overrides(tmp_path: Path) -> None:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    _write_candidate_projection_evidence(tmp_path)
    holdout_alignment = _write_raw_alignment_override(tmp_path, "tier_3_holdout", 2025)
    forward_alignment = _write_raw_alignment_override(tmp_path, "tier_3_forward", 2026)

    report = diagnostic_plan.build_report(
        repo_root=tmp_path,
        proposal_path=fixtures._write_proposal(tmp_path),
        diagnostic_reports_root=tmp_path / "reports" / "pipeline_audit" / "diagnostic_v1",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report="reports/raw_ingest/raw_dbn_alignment.json",
        raw_alignment_report_overrides={
            "tier_3_holdout:2025": holdout_alignment.as_posix(),
            "tier_3_forward:2026": forward_alignment.as_posix(),
        },
    )

    assert report["summary"]["status"] == diagnostic_plan.STATUS_READY
    assert report["summary"]["raw_alignment_report_count"] == 2
    assert report["summary"]["raw_alignment_report_override_count"] == 2
    groups = {group["profile"]: group for group in report["diagnostic_groups"]}
    assert groups["tier_3_holdout"]["raw_alignment_report"] == holdout_alignment.as_posix()
    assert groups["tier_3_forward"]["raw_alignment_report"] == forward_alignment.as_posix()
    assert f"--raw-alignment-report {holdout_alignment.as_posix()}" in groups["tier_3_holdout"]["command"]
    assert f"--raw-alignment-report {forward_alignment.as_posix()}" in groups["tier_3_forward"]["command"]


def test_candidate_projection_blockers_fail_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, projected=False)

    assert report["summary"]["status"] == diagnostic_plan.STATUS_NO_GO
    assert report["summary"]["diagnostic_group_count"] == 0
    assert report["summary"]["generated_output_count"] == 0
    assert any(
        check["name"] == "candidate_projection_blockers_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == diagnostic_plan.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_reports_root_outside_reports_fails_closed(tmp_path: Path) -> None:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    _write_candidate_projection_evidence(tmp_path)
    raw_alignment = _write_raw_alignment_placeholder(tmp_path)

    report = diagnostic_plan.build_report(
        repo_root=tmp_path,
        proposal_path=fixtures._write_proposal(tmp_path),
        diagnostic_reports_root=tmp_path / "diagnostic_v1",
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=[],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
        raw_alignment_report=raw_alignment.as_posix(),
    )

    assert report["summary"]["status"] == diagnostic_plan.STATUS_NO_GO
    assert any(
        check["name"] == "diagnostic_reports_root_under_reports"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_diagnostic_reports(tmp_path: Path, capsys) -> None:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    _write_candidate_projection_evidence(tmp_path)
    proposal = fixtures._write_proposal(tmp_path)
    raw_alignment = _write_raw_alignment_placeholder(tmp_path)
    reports_root = tmp_path / "reports" / "pipeline_audit" / "diagnostic_v1"
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = diagnostic_plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--diagnostic-reports-root",
            str(reports_root),
            "--raw-alignment-report",
            str(raw_alignment),
            "--expected-eligible-market-count",
            "2",
            "--expected-proof-status-market-year-count",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{diagnostic_plan.STAGE} status={diagnostic_plan.STATUS_READY}" in output
    assert "diagnostic_groups=2" in output
    assert "generated_outputs=0" in output
    assert not reports_root.exists()
