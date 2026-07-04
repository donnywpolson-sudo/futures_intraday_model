from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ledger_payload() -> dict[str, object]:
    tier1_path = "reports/pipeline_audit/tier1.json"
    candidate_first = "reports/pipeline_audit/local_trade_shards/NG_2025_w01.json"
    candidate_second = "reports/pipeline_audit/local_trade_shards/NG_2025_w02.json"
    return {
        "summary": {
            "stage": ledger_gate.STAGE,
            "status": ledger_gate.STATUS_READY,
            "accepted_market_year_count": 3,
            "uncovered_canonical_market_count": 2,
            "unselected_report_count": 2,
            "excluded_report_count": 1,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
        },
        "checks": [
            {"name": "input_reports_readable", "status": "PASS"},
            {"name": "candidate_root_classified_not_promoted", "status": "PASS"},
        ],
        "input_reports": [
            {
                "path": tier1_path,
                "sha256": "a" * 64,
                "role": "tier1_repaired",
                "root_classification": "repaired_tier1_convention_evidence",
                "status": "PASS",
            },
            {
                "path": candidate_first,
                "sha256": "b" * 64,
                "role": "candidate_recovery_shard",
                "root_classification": "candidate_derived_review_evidence",
                "status": "PASS",
            },
            {
                "path": candidate_second,
                "sha256": "c" * 64,
                "role": "candidate_recovery_shard",
                "root_classification": "candidate_derived_review_evidence",
                "status": "PASS",
            },
        ],
        "coverage": {
            "accepted_market_years": ["ES:2025", "ES:2026", "NG:2025"],
            "accepted_markets": ["ES", "NG"],
            "canonical_markets": ["ES", "NG", "NQ", "RTY"],
            "uncovered_canonical_markets": ["NQ", "RTY"],
            "rows": [
                {
                    "market": "ES",
                    "year": 2025,
                    "report_path": tier1_path,
                    "report_role": "tier1_repaired",
                    "root_classification": "repaired_tier1_convention_evidence",
                    "causal_root": ledger_gate.TIER1_CAUSAL_ROOT,
                    "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
                    "status": "PASS",
                },
                {
                    "market": "ES",
                    "year": 2026,
                    "report_path": tier1_path,
                    "report_role": "tier1_repaired",
                    "root_classification": "repaired_tier1_convention_evidence",
                    "causal_root": ledger_gate.TIER1_CAUSAL_ROOT,
                    "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
                    "status": "PASS",
                },
                {
                    "market": "NG",
                    "year": 2025,
                    "report_path": candidate_first,
                    "report_role": "candidate_recovery_shard",
                    "root_classification": "candidate_derived_review_evidence",
                    "causal_root": ledger_gate.CANDIDATE_CAUSAL_ROOT,
                    "window": {"start": "2025-06-18T00:00:00Z", "end": "2025-06-25T00:00:00Z"},
                    "status": "PASS",
                },
                {
                    "market": "NG",
                    "year": 2025,
                    "report_path": candidate_second,
                    "report_role": "candidate_recovery_shard",
                    "root_classification": "candidate_derived_review_evidence",
                    "causal_root": ledger_gate.CANDIDATE_CAUSAL_ROOT,
                    "window": {"start": "2025-06-25T00:00:00Z", "end": "2025-07-02T00:00:00Z"},
                    "status": "PASS",
                },
            ],
        },
        "unselected_reports": [
            "reports/pipeline_audit/local_trade_shards/NQ_2025.json",
            "reports/pipeline_audit/local_trade_shards/RTY_2025.json",
        ],
        "excluded_reports": [
            {
                "path": "reports/pipeline_audit/local_trade_shards/RB_2025.json",
                "status": "FAIL",
                "failures": ["--max-runtime-seconds limit exceeded"],
                "root_classification": "superseded_excluded_not_accepted",
            }
        ],
        "non_approval": {
            "scope": "generated review ledger only",
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
        },
    }


def _write_ledger(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "ledger.json"
    _write_json(path, payload or _ledger_payload())
    return path


def _build(tmp_path: Path, payload: dict[str, object] | None = None, staged: list[str] | None = None) -> dict[str, object]:
    return proposal.build_report(
        repo_root=tmp_path,
        ledger_path=_write_ledger(tmp_path, payload),
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
    )


def test_success_collapses_accepted_coverage_and_preserves_lists(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == proposal.STATUS_READY
    assert report["summary"]["proposal_row_count"] == 3
    assert report["summary"]["proof_status_promoted"] is False
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["uncovered_canonical_markets"] == ["NQ", "RTY"]
    assert report["unselected_reports"] == [
        "reports/pipeline_audit/local_trade_shards/NQ_2025.json",
        "reports/pipeline_audit/local_trade_shards/RTY_2025.json",
    ]
    assert report["excluded_reports"][0]["root_classification"] == "superseded_excluded_not_accepted"
    ng_row = next(row for row in report["proposal_rows"] if row["market"] == "NG")
    assert ng_row["source_classifications"] == ["candidate_derived_review_evidence"]
    assert len(ng_row["source_reports"]) == 2
    assert len(ng_row["evidence_windows"]) == 2


def test_write_report_keeps_non_approval_text_and_outputs_under_reports(tmp_path: Path) -> None:
    report = _build(tmp_path)
    json_out = tmp_path / "reports" / "pipeline_audit" / "proposal.json"
    md_out = tmp_path / "reports" / "pipeline_audit" / "proposal.md"

    proposal.write_report(report, repo_root=tmp_path, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == proposal.STATUS_READY
    assert payload["summary"]["canonical_promotion_approved"] is False
    assert "read-only generated proposal" in markdown
    assert "`candidate_derived_review_evidence`" in markdown
    assert "`proof_status_promoted`: `false`" in markdown


def test_ledger_not_review_ready_fails_closed(tmp_path: Path) -> None:
    payload = _ledger_payload()
    payload["summary"]["status"] = ledger_gate.STATUS_NO_GO

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(check["name"] == "input_ledger_review_ready" for check in report["checks"] if check["status"] == "FAIL")


def test_ledger_check_failure_fails_closed(tmp_path: Path) -> None:
    payload = _ledger_payload()
    payload["checks"][0]["status"] = "FAIL"

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(check["name"] == "input_ledger_checks_pass" for check in report["checks"] if check["status"] == "FAIL")


def test_candidate_relabeling_fails_closed(tmp_path: Path) -> None:
    payload = _ledger_payload()
    candidate_row = payload["coverage"]["rows"][2]
    candidate_row["root_classification"] = "repaired_tier1_convention_evidence"

    report = _build(tmp_path, payload)

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_rows_preserve_review_classification"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_path_fails_closed_without_setting_approval_flag(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == proposal.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert report["staged_generated_paths"] == ["reports/pipeline_audit/generated.json"]
    assert any(
        check["name"] == "staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_output_path_outside_reports_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    with pytest.raises(ValueError, match="output path must be under reports"):
        proposal.write_report(
            report,
            repo_root=tmp_path,
            json_out=tmp_path / "proposal.json",
            markdown_out=tmp_path / "reports" / "pipeline_audit" / "proposal.md",
        )
