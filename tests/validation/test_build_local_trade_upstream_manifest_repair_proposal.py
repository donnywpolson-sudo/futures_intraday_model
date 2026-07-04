from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_upstream_manifest_repair_proposal as repair_proposal
from scripts.validation import build_local_trade_upstream_manifest_evidence_resolver as resolver
from tests.validation import test_build_local_trade_upstream_manifest_evidence_resolver as fixtures


def _build(tmp_path: Path, *, staged: list[str] | None = None) -> dict[str, object]:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    return repair_proposal.build_report(
        repo_root=tmp_path,
        proposal_path=fixtures._write_proposal(tmp_path),
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
    )


def test_builds_console_only_repair_proposals_from_resolver_groups(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == repair_proposal.STATUS_READY
    assert report["summary"]["input_resolver_status"] == resolver.STATUS_PLAN_READY
    assert report["summary"]["proposal_item_count"] == 4
    assert report["summary"]["candidate_projection_proposal_count"] == 2
    assert report["summary"]["repaired_warning_proposal_count"] == 2
    assert report["summary"]["selected_warning_row_count"] == 2
    assert report["summary"]["generated_report_written"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["manifest_projection_approved"] is False
    assert report["summary"]["accepted_warning_packet_approved"] is False
    assert report["summary"]["causal_base_repair_approved"] is False
    assert report["summary"]["label_build_approved"] is False

    candidate_items = [
        item
        for item in report["proposal_items"]
        if item["action"] == repair_proposal.ACTION_CANDIDATE_PROJECTION
    ]
    repaired_items = [
        item
        for item in report["proposal_items"]
        if item["action"] == repair_proposal.ACTION_REPAIRED_WARNING
    ]
    assert {item["year"] for item in candidate_items} == {2025, 2026}
    assert all(item["source_profile"] == "all_raw" for item in candidate_items)
    assert all(item["proposal_status"] == repair_proposal.PROPOSAL_STATUS_APPROVAL_REQUIRED for item in candidate_items)
    assert {item["year"] for item in repaired_items} == {2025, 2026}
    assert all(item["existing_phase3_acceptance_support_reusable"] is False for item in repaired_items)
    assert all(item["metadata_blockers"] for item in repaired_items)
    assert any(
        option["option"] == "accepted_warning_packet_plus_manifest_metadata_projection"
        and option["sufficient_by_itself"] is False
        for item in repaired_items
        for option in item["proposed_repair_options"]
    )
    assert report["phase3_existing_warning_acceptance_support"]["reusable_for_local_trade_repaired_root"] is False


def test_staged_generated_path_is_no_go_without_approval_flag(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == repair_proposal.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_repair_proposal_report(tmp_path: Path, capsys) -> None:
    fixtures._write_prerequisites(tmp_path)
    fixtures._write_manifest_evidence(tmp_path)
    proposal = fixtures._write_proposal(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = repair_proposal.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--expected-eligible-market-count",
            "2",
            "--expected-proof-status-market-year-count",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{repair_proposal.STAGE} status={repair_proposal.STATUS_READY}" in output
    assert "proposal_items=4" in output
    assert "generated_outputs=0" in output
    assert not list((tmp_path / "reports").glob(f"**/{repair_proposal.STAGE}*"))
