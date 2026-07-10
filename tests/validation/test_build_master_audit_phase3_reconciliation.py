from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase3_reconciliation as phase3


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _hash(market: str, year: int, prefix: str = "label") -> str:
    return f"{prefix}-{market}-{year}".ljust(64, "0")[:64]


def _active_hashes() -> dict[str, str]:
    return {
        phase3.active_label_path(market, year): _hash(market, year)
        for market, year in phase3.expected_pairs()
    }


def _staged_hashes() -> dict[str, str]:
    return {
        phase3.staged_label_path(market, year): _hash(market, year)
        for market, year in phase3.expected_pairs()
    }


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
        },
        "run_status_table": [
            {
                "audit_area": "Phase 3",
                "run_status": "RUN",
                "detail_status": "RUN_LIMITED_SCOPE_TARGET_TIMING_EVIDENCE",
                "evidence_state": "limited-scope",
                "accepted_evidence": [],
                "scope": "active v2 Tier 1 core labels/features, 6E/CL/ES/ZN, 2023/2024",
                "notes": [],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {"status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY", "summary": {"failure_count": 0}}


def _phase1b_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase1b_master_audit_status": "RUN_LIMITED_SCOPE_PHASE1B_RAW_DBN_RECONCILIATION",
        },
    }


def _phase2_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase2_master_audit_status": "RUN_LIMITED_SCOPE_PHASE2_ACTIVE_CAUSAL_HASH_LINEAGE_RECONCILIATION",
            "phase2_limited_active_hash_lineage_ready": True,
            "phase2_full_master_audit_accepted": False,
            "model_trust_ready": False,
        },
    }


def _phase6_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase6_master_audit_status": "RUN_LIMITED_SCOPE_PHASE6_REPORT_ONLY_WFA_RECONCILIATION",
            "model_trust_ready": False,
        },
    }


def _phase7_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase7_master_audit_status": "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION",
            "model_trust_ready": False,
        },
    }


def _label_semantics() -> dict[str, str]:
    return {
        "diagnostic_ret_ticks_15m": "optional diagnostic only; not a primary target",
        "label_semantics_id": phase3.EXPECTED_LABEL_SEMANTICS_ID,
        "target_accept_any_30m": "primary 30m side-aware acceptance",
        "target_apex_confirmed_any_30m_60m": "same side accepted by both horizons",
        "target_ret_ticks_30m": "primary 30m signed move",
        "target_ret_ticks_60m": "independent robustness signed move",
    }


def _staged_label_manifest() -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "all_causal",
        "resolved_profile": "all_causal",
        "input_root": "data/causally_gated_normalized",
        "output_root": "data/labeled_rebuild_staging/phase3_v2_apex_30m60m_20260709_tier1_core",
        "markets": list(phase3.EXPECTED_MARKETS),
        "years": list(phase3.EXPECTED_YEARS),
        "failure_count": 0,
        "warning_count": 0,
        "causal_base_manifest_gate": {"status": "PASS"},
        "label_semantics": _label_semantics(),
        "input_file_hashes": {
            f"data/causally_gated_normalized/{market}/{year}.parquet": f"causal-{market}-{year}"
            for market, year in phase3.expected_pairs()
        },
        "output_file_hashes": _staged_hashes(),
        "outputs": [
            {"market": market, "year": year, "status": "PASS"}
            for market, year in phase3.expected_pairs()
        ],
    }


def _staged_label_report() -> dict[str, object]:
    return {
        "status": "PASS",
        "summary": {
            "file_count": 8,
            "pass_count": 8,
            "warn_count": 0,
            "fail_count": 0,
            "input_rows": 1000,
            "output_rows": 1000,
            "target_valid_rows": 800,
            "target_invalid_rows": 200,
            "invalid_reason_counts": {"synthetic_path": 200},
            "roll_protection_unavailable_files": 0,
            "roll_detection_unavailable_rows": 0,
        },
        "files": [
            {"market": market, "year": year, "status": "PASS"}
            for market, year in phase3.expected_pairs()
        ],
    }


def _active_replacement_hashes() -> dict[str, object]:
    return {
        "status": "PASS_ACTIVE_LABEL_REPLACEMENT_V2_CORE_NO_DOWNSTREAM",
        "label_semantics_id": phase3.EXPECTED_LABEL_SEMANTICS_ID,
        "scope": {"file_count": 8, "markets": list(phase3.EXPECTED_MARKETS), "years": list(phase3.EXPECTED_YEARS)},
        "failures": [],
        "records": [
            {
                "market": market,
                "year": year,
                "active_path": phase3.active_label_path(market, year),
                "active_sha256": _hash(market, year),
                "staged_sha256": _hash(market, year),
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            }
            for market, year in phase3.expected_pairs()
        ],
    }


def _active_label_manifest(output_hashes: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/causally_gated_normalized",
        "output_root": "data/labeled",
        "markets": list(phase3.EXPECTED_MARKETS),
        "years": list(phase3.EXPECTED_YEARS),
        "failure_count": 0,
        "warning_count": 0,
        "causal_base_manifest_gate": {"status": "PASS"},
        "label_semantics": _label_semantics(),
        "input_file_hashes": {
            f"data/causally_gated_normalized/{market}/{year}.parquet": f"causal-{market}-{year}"
            for market, year in phase3.expected_pairs()
        },
        "output_file_hashes": output_hashes or _active_hashes(),
        "outputs": [
            {"market": market, "year": year, "status": "PASS"}
            for market, year in phase3.expected_pairs()
        ],
    }


def _target_timing_audit(warnings: list[str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS_TARGET_TIMING_AUDIT",
        "summary": {
            "status": "PASS_TARGET_TIMING_AUDIT",
            "commands_executed": 0,
            "completed_bar_convention_assumed": True,
            "data_model_or_prediction_mutation": False,
            "entry_30m_not_after_ts": 0,
            "entry_60m_not_after_ts": 0,
            "exit_30m_offset_mismatches": 0,
            "exit_60m_offset_mismatches": 0,
            "failure_count": 0,
            "pair_count": 8,
            "row_count": 1000,
            "row_key_mismatches": 0,
            "same_session_30m_violations": 0,
            "same_session_60m_violations": 0,
            "valid_30m_rows": 800,
            "valid_60m_rows": 700,
            "warning_count": 1,
        },
        "warnings": warnings if warnings is not None else [phase3.KNOWN_TIMING_WARNING],
        "failures": [],
    }


def _feature_manifest(input_hashes: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "input_root": "data/labeled",
        "output_root": "data/feature_matrices",
        "feature_count": 114,
        "failure_count": 0,
        "warning_count": 0,
        "label_manifest_gate": {
            "status": "PASS",
            "manifest_path": phase3.ACTIVE_LABEL_MANIFEST.as_posix(),
        },
        "input_file_hashes": input_hashes or _active_hashes(),
        "output_file_hashes": {
            f"data/feature_matrices/{market}/{year}.parquet": f"feature-{market}-{year}"
            for market, year in phase3.expected_pairs()
        },
    }


def _target_cols(extra: list[str] | None = None) -> list[str]:
    required = [
        "target_ret_ticks_30m",
        "target_ret_ticks_60m",
        "target_exit_ts_30m",
        "target_exit_ts_60m",
        "target_30m_valid",
        "target_60m_valid",
        "diagnostic_ret_ticks_15m",
    ]
    filler = [f"target_fixture_{idx}" for idx in range(phase3.EXPECTED_TARGET_COUNT - len(required))]
    return required + filler + (extra or [])


def _feature_cols(extra: list[str] | None = None) -> list[str]:
    return [f"feature_fixture_{idx}" for idx in range(phase3.EXPECTED_FEATURE_COUNT)] + (extra or [])


def _base_repo(
    tmp_path: Path,
    *,
    active_manifest: dict[str, object] | None = None,
    feature_manifest: dict[str, object] | None = None,
    timing: dict[str, object] | None = None,
    target_cols: list[str] | None = None,
    feature_cols: list[str] | None = None,
) -> Path:
    _write_text(
        tmp_path / "MASTER_AUDIT.md",
        "Label Timing Label Horizons Invalid Row Rules Cost Assumptions "
        "Label Realizability Label Stability signal_timestamp < execution_timestamp < label_start < label_end\n",
    )
    _write_text(
        tmp_path / "PROJECT_OUTLINE.md",
        f"{phase3.EXPECTED_LABEL_SEMANTICS_ID} 30m primary horizon 60m robustness horizon "
        "target columns diagnostic only target, label, or forward-return columns can enter feature registries\n",
    )
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_json(tmp_path / phase3.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase3.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(tmp_path / phase3.DEFAULT_PHASE1B, _phase1b_payload())
    _write_json(tmp_path / phase3.DEFAULT_PHASE2, _phase2_payload())
    _write_json(tmp_path / phase3.DEFAULT_PHASE6, _phase6_payload())
    _write_json(tmp_path / phase3.DEFAULT_PHASE7, _phase7_payload())
    _write_json(tmp_path / phase3.STAGED_LABEL_MANIFEST, _staged_label_manifest())
    _write_json(tmp_path / phase3.STAGED_LABEL_REPORT, _staged_label_report())
    _write_json(tmp_path / phase3.ACTIVE_REPLACEMENT_HASHES, _active_replacement_hashes())
    _write_json(tmp_path / phase3.ACTIVE_LABEL_MANIFEST, active_manifest or _active_label_manifest())
    _write_json(tmp_path / phase3.TARGET_TIMING_AUDIT, timing or _target_timing_audit())
    _write_json(tmp_path / phase3.FEATURE_MANIFEST, feature_manifest or _feature_manifest())
    _write_json(tmp_path / phase3.TARGET_COLS, target_cols or _target_cols())
    _write_json(tmp_path / phase3.FEATURE_COLS, feature_cols or _feature_cols())
    return tmp_path / phase3.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    active_manifest: dict[str, object] | None = None,
    feature_manifest: dict[str, object] | None = None,
    timing: dict[str, object] | None = None,
    target_cols: list[str] | None = None,
    feature_cols: list[str] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(
        tmp_path,
        active_manifest=active_manifest,
        feature_manifest=feature_manifest,
        timing=timing,
        target_cols=target_cols,
        feature_cols=feature_cols,
    )
    return phase3.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase3_reconciliation_passes_limited_label_timing_lineage_without_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase3.PASS_STATUS
    assert (
        report["summary"]["phase3_master_audit_status"]
        == "RUN_LIMITED_SCOPE_PHASE3_ACTIVE_LABEL_TIMING_HASH_LINEAGE_RECONCILIATION"
    )
    assert report["summary"]["staged_active_hash_match_count"] == 8
    assert report["summary"]["active_feature_hash_match_count"] == 8
    assert report["summary"]["target_feature_intersection_count"] == 0
    assert report["summary"]["target_timing_warning_preserved"] is True
    assert report["summary"]["phase3_full_master_audit_accepted"] is False
    assert report["summary"]["label_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_active_feature_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_feature_hashes = _active_hashes()
    bad_feature_hashes[phase3.active_label_path("CL", 2024)] = "bad".ljust(64, "0")

    report = _build(tmp_path, feature_manifest=_feature_manifest(bad_feature_hashes))

    assert report["status"] == phase3.FAIL_STATUS
    assert any("feature manifest" in failure for failure in report["failures"])


def test_unexpected_timing_warning_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, timing=_target_timing_audit(["unexpected warning"]))

    assert report["status"] == phase3.FAIL_STATUS
    assert any("target timing audit" in failure for failure in report["failures"])


def test_target_feature_registry_intersection_fails_closed(tmp_path: Path) -> None:
    target_cols = _target_cols()
    feature_cols = _feature_cols()
    feature_cols[0] = "target_ret_ticks_30m"

    report = _build(tmp_path, target_cols=target_cols, feature_cols=feature_cols)

    assert report["status"] == phase3.FAIL_STATUS
    assert any("target/feature registry" in failure for failure in report["failures"])


def test_label_report_warning_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    bad_report = _staged_label_report()
    bad_report["summary"]["warn_count"] = 1
    _write_json(tmp_path / phase3.STAGED_LABEL_REPORT, bad_report)

    report = phase3.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase3.FAIL_STATUS
    assert any("label report" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase3.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase3.REPORT_JSON,
        phase3.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase3.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase3_label_build_executed"] is False
    assert payload["non_approval"]["label_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase3.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase3.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
