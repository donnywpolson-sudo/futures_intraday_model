from __future__ import annotations

from pathlib import Path

from scripts.phase2_causal_base import build_causal_base_data as phase2_causal_base
from scripts.validation import build_local_trade_es2026_p1_gap_gate_policy_review as review


def _gap_gate(status: str = review.OBSERVED_MISMATCH_STATUS, reason: str = review.OBSERVED_MISMATCH_REASON) -> dict[str, object]:
    return {
        "status": status,
        "selected_markets": ["ES"],
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "reason": reason,
        "report_paths": {},
        "validation_status_by_market": {"ES": "not_in_local_trades_window_gate_scope"},
        "failures": [],
    }


def _manifest(gate: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "processed_market_year_count": 1,
        "processed_market_years": [{"market": "ES", "year": 2026}],
        "accepted_exception_count": 1,
        "accepted_exception_failure_count": 0,
        "local_trade_ohlcv_gap_gate": gate or _gap_gate(),
        "outputs": [
            {
                "market": "ES",
                "year": 2026,
                "status": "PASS",
                "local_trade_gap_gate_status": review.OBSERVED_MISMATCH_STATUS,
            }
        ],
        "summary": {"local_trade_ohlcv_gap_gate_status": review.OBSERVED_MISMATCH_STATUS},
    }


def _validation(gate: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "accepted_exception_count": 1,
        "accepted_exception_failure_count": 0,
        "local_trade_ohlcv_gap_gate": gate or _gap_gate(),
        "files": [
            {
                "market": "ES",
                "year": 2026,
                "status": "PASS",
                "local_trade_gap_gate_status": review.OBSERVED_MISMATCH_STATUS,
                "vendor_trusted_ohlcv_no_trade_status": review.EXPECTED_VENDOR_BACKED_STATUS,
            }
        ],
        "summary": {
            "file_count": 1,
            "fail_count": 0,
            "local_trade_ohlcv_gap_gate_status": review.OBSERVED_MISMATCH_STATUS,
        },
    }


def _policy_evidence(*, requires: bool = False) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_3_forward",
        "requires_local_trade_gap_gate": requires,
        "mandatory_local_trade_gap_audit_profiles": ["tier_3_forward"] if requires else [],
        "local_trade_gap_audit_profiles": ["tier_3_holdout", "tier_3_forward"],
        "target_profile_in_mandatory_profiles": requires,
        "target_profile_in_audit_profiles": True,
    }


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    return review.build_report(
        repo_root=tmp_path,
        build_reports_root=tmp_path
        / "reports"
        / "pipeline_audit"
        / "local_trade_es2026_p1_causal_base_build_v1",
        output_root=tmp_path
        / "data"
        / "causally_gated_normalized"
        / "local_trade_es2026_p1_candidate",
        profile_config=tmp_path / "configs" / "alpha_tiered.yaml",
        manifest_report=overrides.get("manifest_report", _manifest()),
        validation_report=overrides.get("validation_report", _validation()),
        profile_policy_evidence=overrides.get("profile_policy_evidence", _policy_evidence()),
        proposal_gap_gate_postcondition=overrides.get(
            "proposal_gap_gate_postcondition",
            {
                "status": "PASS",
                "profile": "tier_3_forward",
                "requires_local_trade_gap_gate": False,
                "expected_status": "SKIPPED",
                "expected_reason": "profile_not_required",
                "expected_report_count": 0,
                "expected_report_paths": [],
                "expected_vendor_backed_status": review.EXPECTED_VENDOR_BACKED_STATUS,
                "policy_basis": "vendor_backed_ohlcv_provenance_policy",
            },
        ),
        proposal_expected_gap_gate_status=overrides.get(
            "proposal_expected_gap_gate_status",
            review.OBSERVED_MISMATCH_STATUS,
        ),
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
    )


def test_ready_review_identifies_policy_aligned_skipped_gate_without_execution(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == review.STATUS_READY
    assert report["summary"]["proposal_expected_gap_gate_status"] == "SKIPPED"
    assert report["summary"]["observed_gap_gate_status"] == phase2_causal_base.LOCAL_TRADE_GAP_SKIPPED_STATUS
    assert report["summary"]["observed_gap_gate_reason"] == "profile_not_required"
    assert report["summary"]["source_requires_local_trade_gap_gate"] is False
    assert report["summary"]["postcondition_alignment_status"] == "ALIGNED"
    assert report["summary"]["expected_gap_report_count"] == 0
    assert report["summary"]["missing_expected_gap_report_count"] == 2
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["non_approval"]["changed_gap_gate_policy"] is False
    assert report["postcondition_review"]["gap_gate_policy_blocker_resolved"] is True
    assert report["postcondition_review"]["current_candidate_gap_gate_postcondition_satisfied"] is True
    assert (
        report["postcondition_review"]["downstream_execution_requires_separate_bounded_approval"]
        is True
    )


def test_gap_gate_pass_is_not_the_current_mismatch(tmp_path: Path) -> None:
    gate = _gap_gate(status="PASS", reason="local_trade_reports_passed")

    report = _build(tmp_path, manifest_report=_manifest(gate), validation_report=_validation(gate))

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert any(
        check["name"] == "observed_gap_gate_matches_policy_postcondition"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_source_policy_already_requiring_gate_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, profile_policy_evidence=_policy_evidence(requires=True))

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert any(
        check["name"] == "source_policy_matches_target_profile_postcondition"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_gap_report_with_skipped_gate_fails_closed(tmp_path: Path) -> None:
    reports_root = (
        tmp_path
        / "reports"
        / "pipeline_audit"
        / "local_trade_es2026_p1_causal_base_build_v1"
    )
    reports_root.mkdir(parents=True)
    (reports_root / phase2_causal_base.LOCAL_TRADE_GAP_AUDIT_JSON).write_text(
        "{}",
        encoding="utf-8",
    )

    report = _build(tmp_path)

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["existing_expected_gap_report_count"] == 1
    assert any(
        check["name"] == "expected_gap_reports_match_postcondition"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_staged_generated_artifact_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, staged_generated_paths=["reports/generated.json"])

    assert report["summary"]["status"] == review.STATUS_NO_GO
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_review_packet_is_compact_and_non_executing(tmp_path: Path) -> None:
    report = _build(tmp_path)
    packet = review.review_packet(report)

    assert packet["stage"] == review.STAGE
    assert packet["status"] == review.STATUS_READY
    assert packet["observed_gap_gate_status"] == review.OBSERVED_MISMATCH_STATUS
    assert packet["postcondition_alignment_status"] == "ALIGNED"
    assert packet["generated_artifact_hygiene"] == {
        "generated_output_count": 0,
        "staged_generated_path_count": 0,
    }
    assert packet["postcondition_review"]["gap_gate_policy_blocker_resolved"] is True
