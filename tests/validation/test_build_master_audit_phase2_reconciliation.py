from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase2_reconciliation as phase2


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
                "audit_area": "Phase 2",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "evidence_state": "unknown",
                "accepted_evidence": [],
                "scope": "causal/session-normalization audit not executed here",
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
            "phase2_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _phase6_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase6_master_audit_status": "RUN_LIMITED_SCOPE_PHASE6_REPORT_ONLY_WFA_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _phase7_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase7_master_audit_status": "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _active_hashes() -> dict[str, str]:
    return {
        phase2.causal_path(market, year): _hash(market, year)
        for market, year in phase2.expected_pairs()
    }


def _legacy_hashes() -> dict[str, str]:
    return {
        phase2.causal_path(market, year): _hash(market, year, "legacy")
        for market, year in phase2.expected_pairs()
    }


def _active_manifest() -> dict[str, object]:
    hashes = _active_hashes()
    return {
        "status": "PASS",
        "profile": "all_causal",
        "resolved_profile": "all_causal",
        "output_root": "data/causally_gated_normalized",
        "summary": {"output_count": 518, "fail_count": 0, "warn_count": 0},
        "output_file_hashes": hashes,
        "outputs": [
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "output_path": phase2.causal_path(market, year),
                "output_sha256": hashes[phase2.causal_path(market, year)],
                "warning_count": 0,
                "failure_count": 0,
            }
            for market, year in phase2.expected_pairs()
        ],
    }


def _legacy_manifest() -> dict[str, object]:
    return {
        "status": "WARN",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": list(phase2.EXPECTED_MARKETS),
        "years": list(phase2.EXPECTED_YEARS),
        "warning_count": 4,
        "failure_count": 0,
        "selected_input_count": 8,
        "output_root": "data/causally_gated_normalized",
        "output_file_hashes": _legacy_hashes(),
        "outputs": [
            {"market": market, "year": year, "status": "WARN"}
            for market, year in phase2.expected_pairs()
        ],
    }


def _legacy_validation() -> dict[str, object]:
    return {
        "status": "WARN",
        "profile": "tier_1",
        "warning_count": 4,
        "failure_count": 0,
        "files": [
            {"market": market, "year": year, "status": "WARN"}
            for market, year in phase2.expected_pairs()
        ],
    }


def _gate_report() -> dict[str, object]:
    return {
        "status": "PASS_MANIFEST_GATE_READY_NO_EXECUTION",
        "summary": {
            "manifest_status": "PASS",
            "gate_check_status": "PASS",
            "active_causal_pair_count": 518,
            "raw_to_causal_status": "WARN",
            "provider_network_calls": False,
            "data_mutation_performed": False,
            "feature_wfa_prediction_modeling_performed": False,
        },
    }


def _readiness_payload(
    raw_without_causal: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "summary": {
            "status": "WARN",
            "severe_blocker_count": 0,
            "raw_without_causal_count": 8,
            "causal_rebuild_approved": False,
            "data_mutation_performed": False,
            "labels_features_wfa_predictions_modeling_approved": False,
            "local_trade_gap_gate_status_counts": {"NOT_RUN": 512, "SKIPPED": 6},
        },
        "raw_without_causal": raw_without_causal
        if raw_without_causal is not None
        else [{"market": market, "year": year} for market in phase2.EXPECTED_MARKETS for year in (2025, 2026)],
        "blockers": [
            {"severity": "Medium", "blocker": "Some active raw pairs have no active causal output."}
        ],
    }


def _label_manifest(input_hashes: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/causally_gated_normalized",
        "output_root": "data/labeled",
        "markets": list(phase2.EXPECTED_MARKETS),
        "years": list(phase2.EXPECTED_YEARS),
        "failure_count": 0,
        "warning_count": 0,
        "causal_base_manifest_gate": {
            "status": "PASS",
            "manifest_path": phase2.ACTIVE_CAUSAL_MANIFEST.as_posix(),
            "expected_market_year_count": 8,
        },
        "input_file_hashes": input_hashes or _active_hashes(),
    }


def _base_repo(
    tmp_path: Path,
    *,
    active_manifest: dict[str, object] | None = None,
    label_manifest: dict[str, object] | None = None,
    legacy_manifest: dict[str, object] | None = None,
    readiness: dict[str, object] | None = None,
) -> Path:
    _write_text(
        tmp_path / "MASTER_AUDIT.md",
        "Session Normalization missing-data markers Indicator Warmup Rules "
        "bar_available_ts invalid-row handling row counts "
        "source_timestamp <= prediction_timestamp\n",
    )
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "project outline\n")
    _write_text(
        tmp_path / phase2.PHASE2_SPEC,
        "bar_available_ts phase2_ready causal_valid raw_row_present "
        "source_path source_file_hash source_row_number\n",
    )
    _write_json(tmp_path / phase2.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase2.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(tmp_path / phase2.DEFAULT_PHASE1B, _phase1b_payload())
    _write_json(tmp_path / phase2.DEFAULT_PHASE6, _phase6_payload())
    _write_json(tmp_path / phase2.DEFAULT_PHASE7, _phase7_payload())
    _write_json(tmp_path / phase2.LEGACY_CAUSAL_MANIFEST, legacy_manifest or _legacy_manifest())
    _write_json(tmp_path / phase2.LEGACY_CAUSAL_VALIDATION, _legacy_validation())
    _write_json(tmp_path / phase2.ACTIVE_CAUSAL_GATE_REPORT, _gate_report())
    _write_json(tmp_path / phase2.ACTIVE_CAUSAL_MANIFEST, active_manifest or _active_manifest())
    _write_json(tmp_path / phase2.READINESS_POST_EXCLUSIONS, readiness or _readiness_payload())
    _write_json(tmp_path / phase2.V2_LABEL_MANIFEST, label_manifest or _label_manifest())
    return tmp_path / phase2.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    active_manifest: dict[str, object] | None = None,
    label_manifest: dict[str, object] | None = None,
    legacy_manifest: dict[str, object] | None = None,
    readiness: dict[str, object] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(
        tmp_path,
        active_manifest=active_manifest,
        label_manifest=label_manifest,
        legacy_manifest=legacy_manifest,
        readiness=readiness,
    )
    return phase2.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase2_reconciliation_passes_limited_hash_lineage_without_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase2.PASS_STATUS
    assert (
        report["summary"]["phase2_master_audit_status"]
        == "RUN_LIMITED_SCOPE_PHASE2_ACTIVE_CAUSAL_HASH_LINEAGE_RECONCILIATION"
    )
    assert report["summary"]["active_hash_match_count"] == 8
    assert report["summary"]["legacy_hash_mismatch_count"] == 8
    assert report["summary"]["phase2_full_master_audit_accepted"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["causal_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_active_label_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_hashes = _active_hashes()
    bad_hashes[phase2.causal_path("ES", 2024)] = "bad".ljust(64, "0")

    report = _build(tmp_path, label_manifest=_label_manifest(bad_hashes))

    assert report["status"] == phase2.FAIL_STATUS
    assert any("active causal manifest hashes" in failure for failure in report["failures"])


def test_legacy_causal_base_matching_active_hash_fails_stale_classification(tmp_path: Path) -> None:
    bad_legacy = copy.deepcopy(_legacy_manifest())
    bad_legacy["output_file_hashes"] = _active_hashes()

    report = _build(tmp_path, legacy_manifest=bad_legacy)

    assert report["status"] == phase2.FAIL_STATUS
    assert any("legacy reports/causal_base" in failure for failure in report["failures"])


def test_scoped_raw_without_causal_blocker_fails_closed(tmp_path: Path) -> None:
    readiness = _readiness_payload(raw_without_causal=[{"market": "6E", "year": 2024}])

    report = _build(tmp_path, readiness=readiness)

    assert report["status"] == phase2.FAIL_STATUS
    assert any("scoped 2023/2024 blocker" in failure for failure in report["failures"])


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
    assert payload["non_approval"]["phase2_build_or_readiness_executed"] is False
    assert payload["non_approval"]["causal_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase2.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase2.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
