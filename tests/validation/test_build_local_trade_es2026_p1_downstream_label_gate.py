from __future__ import annotations

from pathlib import Path

from scripts.validation import build_local_trade_es2026_p1_downstream_label_gate as gate
from scripts.validation import build_local_trade_es2026_p1_gap_gate_policy_review as gap_review


def _gap_review_report(status: str = gap_review.STATUS_READY, alignment: str = "ALIGNED") -> dict[str, object]:
    return {
        "summary": {
            "status": status,
            "postcondition_alignment_status": alignment,
            "market": "ES",
            "year": 2026,
            "profile": "tier_3_forward",
            "proposal_expected_gap_gate_status": "SKIPPED",
            "proposal_expected_gap_gate_reason": "profile_not_required",
            "observed_gap_gate_status": "SKIPPED",
            "observed_gap_gate_reason": "profile_not_required",
            "source_requires_local_trade_gap_gate": False,
            "expected_gap_report_count": 0,
            "missing_expected_gap_report_count": 2,
            "existing_expected_gap_report_count": 0,
            "generated_output_count": 0,
            "staged_generated_path_count": 0,
        },
        "postcondition_review": {"gap_gate_policy_blocker_resolved": True},
    }


def _manifest_evidence(status: str = "PASS") -> dict[str, object]:
    if status != "PASS":
        return {"status": "FAIL", "reason": "manifest mismatch"}
    return {
        "status": "PASS",
        "manifest_status": "PASS",
        "stage": "causal_base",
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "processed_market_year_count": 1,
        "processed_market_years": [{"market": "ES", "year": 2026}],
        "accepted_exception_count": 1,
        "accepted_exception_failure_count": 0,
        "output_exists": True,
        "manifest_output_hash": "a" * 64,
        "actual_output_hash": "a" * 64,
        "output_row": {
            "market": "ES",
            "year": 2026,
            "status": "PASS",
            "vendor_trusted_ohlcv_no_trade_status": gate.gap_review.EXPECTED_VENDOR_BACKED_STATUS,
            "local_trade_gap_gate_status": "SKIPPED",
        },
    }


def _profile_scope(status: str = "PASS") -> dict[str, object]:
    return {
        "status": status,
        "profile": "tier_3_forward",
        "target_market_in_profile": status == "PASS",
        "target_year_in_profile": status == "PASS",
    }


def _cost(status: str = "PASS", provisional: bool = False) -> dict[str, object]:
    if status != "PASS":
        return {"status": "FAIL", "market": "ES", "reason": "missing"}
    return {
        "status": "PASS",
        "market": "ES",
        "tick_size": 0.25,
        "tick_value": 12.5,
        "point_value": 50.0,
        "cost_source": "unit_test",
        "provisional": provisional,
        "estimated_cost_ticks": 2.36,
    }


def _accepted_packet(status: str = "PASS") -> dict[str, object]:
    if status != "PASS":
        return {"status": "FAIL", "reason": "bad packet"}
    return {
        "status": "PASS",
        "profile": "tier_3_forward",
        "accepted_warning": gate.EXPECTED_ACCEPTED_WARNING,
        "packet": {
            "category": gate.EXPECTED_ACCEPTED_EXCEPTION_CATEGORY,
            "market": "ES",
            "year": 2026,
            "reason": gate.EXPECTED_ACCEPTED_EXCEPTION_REASON,
            "evidence_paths": gate.EXPECTED_ACCEPTED_EVIDENCE_PATHS,
            "warning_prefixes": [gate.EXPECTED_ACCEPTED_WARNING],
        },
        "mismatches": {},
    }


def _write_label_script(tmp_path: Path, *, missing_years: bool = False) -> Path:
    flags = [
        "--profile",
        "--input-root",
        "--output-root",
        "--reports-root",
        "--costs-config",
        "--profile-config",
        "--accepted-readiness-exceptions",
        "--markets",
        "--causal-base-manifest",
    ]
    if not missing_years:
        flags.append("--years")
    path = tmp_path / "scripts" / "phase3_labels" / "build_labels.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    args = "\n".join(f'    parser.add_argument("{flag}")' for flag in flags)
    path.write_text(
        "import argparse\n\n"
        "def build_arg_parser():\n"
        "    parser = argparse.ArgumentParser()\n"
        f"{args}\n"
        "    return parser\n",
        encoding="utf-8",
    )
    return path


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "candidate_causal_root": tmp_path
        / "data"
        / "causally_gated_normalized"
        / "local_trade_es2026_p1_candidate",
        "label_output_root": tmp_path / "data" / "labeled" / "local_trade_es2026_p1_candidate",
        "label_reports_root": tmp_path / "reports" / "labels" / "local_trade_es2026_p1_candidate",
        "build_reports_root": tmp_path
        / "reports"
        / "pipeline_audit"
        / "local_trade_es2026_p1_causal_base_build_v1",
        "profile_config": tmp_path / "configs" / "alpha_tiered.yaml",
        "costs_config": tmp_path / "configs" / "costs.yaml",
        "label_script": _write_label_script(tmp_path),
    }


def _ignored(paths: dict[str, Path], tmp_path: Path) -> list[str]:
    return [
        gate.rel(tmp_path / artifact, tmp_path)
        for artifact in gate._expected_label_artifacts(
            output_root=paths["label_output_root"],
            reports_root=paths["label_reports_root"],
        )
    ]


def _build(tmp_path: Path, **overrides) -> dict[str, object]:
    paths = _paths(tmp_path)
    if overrides.get("missing_year_flag"):
        paths["label_script"] = _write_label_script(tmp_path, missing_years=True)
    return gate.build_report(
        repo_root=tmp_path,
        **paths,
        generated_at_utc="2026-07-03T00:00:00Z",
        staged_generated_paths=overrides.get("staged_generated_paths", []),
        ignored_generated_paths=overrides.get("ignored_generated_paths", _ignored(paths, tmp_path)),
        gap_review_report=overrides.get("gap_review_report", _gap_review_report()),
        manifest_evidence=overrides.get("manifest_evidence", _manifest_evidence()),
        profile_scope_evidence=overrides.get("profile_scope_evidence", _profile_scope()),
        cost_evidence=overrides.get("cost_evidence", _cost()),
        accepted_packet_evidence=overrides.get("accepted_packet_evidence", _accepted_packet()),
    )


def test_gate_exposes_bounded_phase3_label_command_with_es2026_warning_packet(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["expected_generated_output_count"] == 3
    assert report["summary"]["ignored_expected_generated_output_count"] == 3
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["commands_executed"] == 0
    assert report["summary"]["label_build_approved"] is False
    assert report["approval_gate"]["approval_token"] == "APPROVE_ES2026_P1_PHASE3_LABEL_BUILD_V1"
    assert (
        "--accepted-readiness-exceptions configs/alpha_tiered.yaml"
        in report["approval_gate"]["exact_command"]
    )
    passed_check = next(
        check
        for check in report["checks"]
        if check["name"] == "phase3_accepted_warning_handling_wired"
    )
    assert passed_check["status"] == "PASS"
    assert passed_check["observed"]["causal_base_manifest_accepted_exception_count"] == 1
    assert (
        passed_check["observed"]["phase3_command_accepted_readiness_exceptions"]
        == "configs/alpha_tiered.yaml"
    )


def test_bad_es2026_warning_packet_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, accepted_packet_evidence=_accepted_packet(status="FAIL"))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "profile_config_contains_approved_es2026_warning_packet"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_gap_review_not_aligned_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        gap_review_report=_gap_review_report(alignment="NOT_ALIGNED"),
    )

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["approval_gate"] == {}
    assert any(
        check["name"] == "gap_gate_review_ready_aligned"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_manifest_mismatch_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, manifest_evidence=_manifest_evidence(status="FAIL"))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "candidate_causal_manifest_exact_es2026_pass"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_provisional_cost_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, cost_evidence=_cost(provisional=True))

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "cost_config_covers_es"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_year_filter_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_year_flag=True)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(
        check["name"] == "phase3_label_cli_has_bounded_controls"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_unignored_expected_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    ignored = _ignored(paths, tmp_path)[:-1]

    report = _build(tmp_path, ignored_generated_paths=ignored)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["unignored_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_label_artifacts_ignored_by_git"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_existing_expected_artifact_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    output_path = paths["label_output_root"] / "ES" / "2026.parquet"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"existing")

    report = _build(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["existing_expected_generated_output_count"] == 1
    assert any(
        check["name"] == "expected_label_artifacts_absent_before_execution"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_gate_packet_is_compact(tmp_path: Path) -> None:
    report = _build(tmp_path)
    packet = gate.gate_packet(report)

    assert packet["stage"] == gate.STAGE
    assert packet["status"] == gate.STATUS_READY
    assert packet["approval_gate"]["approval_token"] == "APPROVE_ES2026_P1_PHASE3_LABEL_BUILD_V1"
    assert packet["generated_artifact_hygiene"]["generated_output_count"] == 0
