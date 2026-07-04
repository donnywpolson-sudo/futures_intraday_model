from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate
from scripts.validation import promote_local_trade_proof_status as promotion


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source_report(path: str, *, classification: str, status: str = "PASS") -> dict[str, object]:
    return {
        "path": path,
        "sha256": "a" * 64,
        "role": "candidate_recovery_shard"
        if classification == "candidate_derived_review_evidence"
        else "tier1_repaired",
        "root_classification": classification,
        "status": status,
    }


def _row(
    market: str,
    year: int,
    *,
    classification: str,
    source_status: str = "PASS",
) -> dict[str, object]:
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
        "source_reports": [
            _source_report(path, classification=classification, status=source_status)
        ],
        "evidence_windows": [
            {
                "report_path": path,
                "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
            }
        ],
    }


def _proposal_payload() -> dict[str, object]:
    rows = [
        _row("ES", 2025, classification="repaired_tier1_convention_evidence"),
        _row("ES", 2026, classification="repaired_tier1_convention_evidence"),
        _row("NG", 2025, classification="candidate_derived_review_evidence"),
    ]
    return {
        "summary": {
            "stage": proposal_gate.STAGE,
            "status": proposal_gate.STATUS_READY,
            "decision": proposal_gate.DECISION_REVIEW_ONLY,
            "proposal_row_count": len(rows),
            "uncovered_canonical_market_count": 2,
            "unselected_report_count": 1,
            "excluded_report_count": 1,
            "staged_generated_path_count": 0,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "failure_count": 0,
        },
        "checks": [
            {"name": "input_ledger_review_ready", "status": "PASS"},
            {"name": "proposal_rows_from_accepted_coverage", "status": "PASS"},
        ],
        "proposal_rows": rows,
        "uncovered_canonical_markets": ["NQ", "RTY"],
        "unselected_reports": ["reports/pipeline_audit/NQ_2025.json"],
        "excluded_reports": [
            {
                "path": "reports/pipeline_audit/RB_2025.json",
                "status": "FAIL",
                "failures": ["--max-runtime-seconds limit exceeded"],
            }
        ],
        "staged_generated_paths": [],
    }


def _write_proposal(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "proposal.json"
    _write_json(path, payload or _proposal_payload())
    return path


def _build(
    tmp_path: Path,
    payload: dict[str, object] | None = None,
    staged: list[str] | None = None,
) -> dict[str, object]:
    return promotion.build_report(
        repo_root=tmp_path,
        proposal_path=_write_proposal(tmp_path, payload),
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
    )


def test_promotes_review_ready_proposal_without_other_approvals(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == promotion.STATUS_PROMOTED
    assert report["summary"]["decision"] == promotion.DECISION_APPROVED
    assert report["summary"]["proof_status_promoted"] is True
    assert report["summary"]["promoted_market_year_count"] == 3
    assert report["summary"]["promoted_market_count"] == 2
    assert report["summary"]["candidate_derived_market_year_count"] == 1
    assert report["summary"]["repaired_tier1_market_year_count"] == 2
    assert report["summary"]["canonical_promotion_approved"] is False
    assert report["summary"]["modeling_approved"] is False
    assert {row["proof_status"] for row in report["proof_status_rows"]} == {
        promotion.PROMOTED_PROOF_STATUS
    }


def test_non_ready_proposal_fails_closed(tmp_path: Path) -> None:
    payload = _proposal_payload()
    payload["summary"]["status"] = proposal_gate.STATUS_NO_GO  # type: ignore[index]

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == promotion.STATUS_NO_GO
    assert report["summary"]["proof_status_promoted"] is False
    assert report["summary"]["promoted_market_year_count"] == 0
    assert any(
        check["name"] == "proposal_review_ready"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_current_staged_generated_path_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == promotion.STATUS_NO_GO
    assert report["summary"]["proof_status_promoted"] is False
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_proposal_with_staged_generated_paths_fails_closed(tmp_path: Path) -> None:
    payload = _proposal_payload()
    payload["summary"]["staged_generated_path_count"] = 1  # type: ignore[index]
    payload["staged_generated_paths"] = ["reports/pipeline_audit/generated.json"]

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == promotion.STATUS_NO_GO
    assert any(
        check["name"] == "proposal_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_source_report_status_must_pass(tmp_path: Path) -> None:
    payload = _proposal_payload()
    payload["proposal_rows"][2] = _row(  # type: ignore[index]
        "NG",
        2025,
        classification="candidate_derived_review_evidence",
        source_status="FAIL",
    )

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == promotion.STATUS_NO_GO
    assert any(check["name"] == "source_reports_pass" for check in report["checks"] if check["status"] == "FAIL")


def test_candidate_root_relabeling_fails_closed(tmp_path: Path) -> None:
    payload = _proposal_payload()
    candidate_row = payload["proposal_rows"][2]  # type: ignore[index]
    candidate_row["source_classifications"] = ["repaired_tier1_convention_evidence"]

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == promotion.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_rows_remain_review_evidence"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_write_report_outputs_promotion_and_non_approval_text(tmp_path: Path) -> None:
    report = _build(tmp_path)
    json_out = tmp_path / "reports" / "pipeline_audit" / "promotion.json"
    md_out = tmp_path / "reports" / "pipeline_audit" / "promotion.md"

    promotion.write_report(report, repo_root=tmp_path, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == promotion.STATUS_PROMOTED
    assert payload["summary"]["canonical_promotion_approved"] is False
    assert "proof-status promotion only" in markdown
    assert promotion.PROMOTED_PROOF_STATUS in markdown
    assert "`modeling_approved`: `false`" in markdown


def test_output_path_outside_reports_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    with pytest.raises(ValueError, match="output path must be under reports"):
        promotion.write_report(
            report,
            repo_root=tmp_path,
            json_out=tmp_path / "promotion.json",
            markdown_out=tmp_path / "reports" / "pipeline_audit" / "promotion.md",
        )
