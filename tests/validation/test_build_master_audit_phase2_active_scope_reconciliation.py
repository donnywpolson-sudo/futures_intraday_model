from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase2_active_scope_reconciliation as phase2


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _hash(market: str, year: int, prefix: str = "active") -> str:
    return f"{prefix}-{market}-{year}".ljust(64, "0")[:64]


def _active_hashes() -> dict[str, str]:
    return {
        phase2.causal_path(market, year): _hash(market, year)
        for market, year in phase2.expected_pairs()
    }


def _phase2_reconciliation() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "phase2_limited_active_hash_lineage_ready": True,
            "phase2_full_master_audit_accepted": False,
            "phase2_session_normalization_audit_accepted": False,
            "phase2_build_or_readiness_accepted": False,
            "audit_phase2_causal_session_normalization_executed": False,
            "phase2_build_or_readiness_executed": False,
            "causal_parquet_read_executed": False,
            "active_scoped_output_count": 8,
            "active_hash_match_count": 8,
            "readiness_status": "WARN",
            "readiness_severe_blocker_count": 0,
            "scoped_raw_without_causal_count": 0,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _gate_report() -> dict[str, object]:
    return {
        "status": "PASS_MANIFEST_GATE_READY_NO_EXECUTION",
        "summary": {
            "status": "PASS_MANIFEST_GATE_READY_NO_EXECUTION",
            "manifest_status": "PASS",
            "gate_check_status": "PASS",
            "active_causal_pair_count": 518,
            "output_count": 518,
            "manifest_failure_count": 0,
            "manifest_warning_count": 0,
            "gate_failure_count": 0,
            "provider_network_calls": False,
            "data_mutation_performed": False,
            "cleanup_archive_execution_performed": False,
            "sidecar_canonicalization_performed": False,
            "label_writes_performed": False,
            "feature_wfa_prediction_modeling_performed": False,
            "commit_push_paper_live_performed": False,
        },
    }


def _active_manifest() -> dict[str, object]:
    hashes = _active_hashes()
    return {
        "status": "PASS",
        "profile": "all_causal",
        "resolved_profile": "all_causal",
        "output_root": "data/causally_gated_normalized",
        "summary": {
            "output_count": 518,
            "active_causal_pair_count": 518,
            "fail_count": 0,
            "warn_count": 0,
        },
        "output_file_hashes": {
            **hashes,
            **{f"data/causally_gated_normalized/X{i}/2024.parquet": f"extra-{i}".ljust(64, "0")[:64] for i in range(510)},
        },
        "outputs": [
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "output_path": phase2.causal_path(market, year),
                "output_sha256": hashes[phase2.causal_path(market, year)],
                "warning_count": 0,
                "warnings": [],
                "failure_count": 0,
                "failures": [],
            }
            for market, year in phase2.expected_pairs()
        ],
    }


def _readiness_payload(
    *,
    severe_blockers: int = 0,
    raw_without_causal: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "summary": {
            "status": "WARN",
            "severe_blocker_count": severe_blockers,
            "raw_without_causal_count": 8,
            "causal_rebuild_approved": False,
            "data_mutation_performed": False,
            "labels_features_wfa_predictions_modeling_approved": False,
            "provider_network_calls": False,
            "local_trade_gap_gate_status_counts": {"NOT_RUN": 512, "SKIPPED": 6},
        },
        "raw_without_causal": raw_without_causal
        if raw_without_causal is not None
        else [
            {"market": market, "year": year}
            for market in phase2.EXPECTED_MARKETS
            for year in (2025, 2026)
        ],
    }


def _label_manifest(input_hashes: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/causally_gated_normalized",
        "output_root": "data/labeled",
        "failure_count": 0,
        "warning_count": 0,
        "causal_base_manifest_gate": {
            "status": "PASS",
            "manifest_path": phase2.ACTIVE_CAUSAL_MANIFEST.as_posix(),
            "expected_market_year_count": 8,
        },
        "input_file_hashes": input_hashes or _active_hashes(),
    }


def _target_timing() -> dict[str, object]:
    return {
        "status": "PASS_TARGET_TIMING_AUDIT",
        "summary": {
            "status": "PASS_TARGET_TIMING_AUDIT",
            "failure_count": 0,
            "warning_count": 1,
            "pair_count": 8,
            "row_count": 2_837_374,
            "row_key_mismatches": 0,
            "entry_30m_not_after_ts": 0,
            "entry_60m_not_after_ts": 0,
            "exit_30m_offset_mismatches": 0,
            "exit_60m_offset_mismatches": 0,
            "same_session_30m_violations": 0,
            "same_session_60m_violations": 0,
            "completed_bar_convention_assumed": True,
            "commands_executed": 0,
            "data_model_or_prediction_mutation": False,
        },
    }


def _base_repo(
    tmp_path: Path,
    *,
    phase2_reconciliation: dict[str, object] | None = None,
    gate_report: dict[str, object] | None = None,
    active_manifest: dict[str, object] | None = None,
    readiness: dict[str, object] | None = None,
    label_manifest: dict[str, object] | None = None,
    target_timing: dict[str, object] | None = None,
) -> Path:
    _write_json(
        tmp_path / phase2.PHASE2_RECONCILIATION,
        phase2_reconciliation or _phase2_reconciliation(),
    )
    _write_json(tmp_path / phase2.ACTIVE_CAUSAL_GATE_REPORT, gate_report or _gate_report())
    _write_json(tmp_path / phase2.ACTIVE_CAUSAL_MANIFEST, active_manifest or _active_manifest())
    _write_json(
        tmp_path / phase2.READINESS_POST_EXCLUSIONS,
        readiness or _readiness_payload(),
    )
    _write_json(tmp_path / phase2.V2_LABEL_MANIFEST, label_manifest or _label_manifest())
    _write_json(tmp_path / phase2.TARGET_TIMING, target_timing or _target_timing())
    _write_text(
        tmp_path / phase2.PHASE2_SPEC,
        "bar_available_ts phase2_ready causal_valid raw_row_present "
        "source_path source_file_hash source_row_number\n",
    )
    return tmp_path / phase2.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    **kwargs: object,
) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, **kwargs)
    return phase2.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )


def test_phase2_active_scope_reconciliation_passes_current_style_evidence(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase2.PASS_STATUS
    assert report["summary"]["causal_session_active_scope_ready"] is True
    assert report["summary"]["active_scoped_output_count"] == 8
    assert report["summary"]["active_hash_match_count"] == 8
    assert report["summary"]["readiness_status"] == "WARN"
    assert report["summary"]["scoped_raw_without_causal_count"] == 0
    assert report["summary"]["target_timing_row_count"] == 2_837_374
    assert report["summary"]["phase2_full_master_audit_accepted"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["causal_parquet_read_executed"] is False


def test_missing_active_manifest_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / phase2.ACTIVE_CAUSAL_MANIFEST).unlink()

    report = phase2.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase2.FAIL_STATUS
    assert any("required JSON input unavailable" in failure for failure in report["failures"])


def test_label_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_hashes = _active_hashes()
    bad_hashes[phase2.causal_path("ES", 2024)] = "bad".ljust(64, "0")

    report = _build(tmp_path, label_manifest=_label_manifest(bad_hashes))

    assert report["status"] == phase2.FAIL_STATUS
    assert any("active causal output hashes" in failure for failure in report["failures"])


def test_target_timing_failure_fails_closed(tmp_path: Path) -> None:
    target = copy.deepcopy(_target_timing())
    target["status"] = "FAIL_TARGET_TIMING_AUDIT"
    target["summary"]["status"] = "FAIL_TARGET_TIMING_AUDIT"  # type: ignore[index]
    target["summary"]["failure_count"] = 1  # type: ignore[index]

    report = _build(tmp_path, target_timing=target)

    assert report["status"] == phase2.FAIL_STATUS
    assert any("target timing audit" in failure for failure in report["failures"])


def test_scoped_raw_without_causal_blocker_fails_closed(tmp_path: Path) -> None:
    readiness = _readiness_payload(
        raw_without_causal=[{"market": "6E", "year": 2024}]
    )

    report = _build(tmp_path, readiness=readiness)

    assert report["status"] == phase2.FAIL_STATUS
    assert any("zero active-scope blocker" in failure for failure in report["failures"])


def test_severe_readiness_blocker_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, readiness=_readiness_payload(severe_blockers=1))

    assert report["status"] == phase2.FAIL_STATUS
    assert any("zero active-scope blocker" in failure for failure in report["failures"])


def test_forbidden_action_flag_fails_closed(tmp_path: Path) -> None:
    gate = copy.deepcopy(_gate_report())
    gate["summary"]["data_mutation_performed"] = True  # type: ignore[index]

    report = _build(tmp_path, gate_report=gate)

    assert report["status"] == phase2.FAIL_STATUS
    assert any("no-execution evidence" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase2.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase2.REPORT_JSON,
        phase2.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase2.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["causal_session_active_scope_ready"] is True
    assert payload["summary"]["model_trust_ready"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase2.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase2.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
