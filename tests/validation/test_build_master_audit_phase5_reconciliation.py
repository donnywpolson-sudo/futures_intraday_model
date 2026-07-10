from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase5_reconciliation as phase5


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _hash(market: str, year: int) -> str:
    return f"feature-{market}-{year}".ljust(64, "0")[:64]


def _feature_hashes() -> dict[str, str]:
    return {
        phase5.feature_matrix_path(market, year): _hash(market, year)
        for market, year in phase5.expected_pairs()
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
                "audit_area": "Phase 5",
                "run_status": "RUN",
                "detail_status": "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD",
                "evidence_state": "limited-scope",
                "scope": "active v2 Tier 1 core split contamination guard, 48 folds",
                "accepted_evidence": [],
                "notes": [],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {"status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY", "summary": {"failure_count": 0}}


def _phase_payload(phase: str, status_value: str, status_key: str) -> dict[str, object]:
    return {
        "status": status_value,
        "summary": {
            "failure_count": 0,
            status_key: f"RUN_LIMITED_SCOPE_PHASE{phase}_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
            f"phase{phase}_full_master_audit_accepted": False,
        },
    }


def _phase4_payload(*, model_trust_ready: bool = False) -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE4_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase4_master_audit_status": "RUN_LIMITED_SCOPE_PHASE4_ACTIVE_FEATURE_LEAKAGE_HASH_LINEAGE_RECONCILIATION",
            "phase4_full_master_audit_accepted": False,
            "model_trust_ready": model_trust_ready,
            "promotion_allowed": False,
        },
    }


def _phase7_payload(*, promotion_allowed: bool = False) -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase7_master_audit_status": "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": promotion_allowed,
        },
    }


def _folds(*, final_holdout: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for market in phase5.EXPECTED_MARKETS:
        for idx in range(phase5.EXPECTED_FOLDS_PER_MARKET):
            fold_number = idx + 1
            rows.append(
                {
                    "market": market,
                    "fold_id": f"{market}_research_{fold_number:04d}",
                    "fold_number": fold_number,
                    "year": 2024,
                    "split_group": "research",
                    "train_start": "2023-01-01T00:00:00+00:00",
                    "train_end": f"2024-{fold_number:02d}-01T20:00:00+00:00",
                    "purged_train_end": f"2024-{fold_number:02d}-01T20:00:00+00:00",
                    "test_start": f"2024-{fold_number:02d}-01T21:00:00+00:00",
                    "test_end": f"2024-{fold_number:02d}-02T21:00:00+00:00",
                    "embargo_end": f"2024-{fold_number:02d}-03T00:00:00+00:00",
                    "train_rows_after_purge": 1000,
                    "test_rows": 100,
                    "purge_bars": 61,
                    "resolved_purge_bars": 61,
                    "embargo_bars": 61,
                    "is_final_holdout": final_holdout and market == "6E" and idx == 0,
                    "final_holdout": final_holdout and market == "6E" and idx == 0,
                    "selection_allowed": True,
                }
            )
    return rows


def _split_plan(*, input_hashes: dict[str, str] | None = None, final_holdout: bool = False) -> dict[str, object]:
    return {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/feature_matrices",
        "output_root": "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core",
        "markets": list(phase5.EXPECTED_MARKETS),
        "years": list(phase5.EXPECTED_YEARS),
        "fold_count": 48,
        "warning_count": 0,
        "failure_count": 0,
        "failures": [],
        "input_file_hashes": input_hashes or _feature_hashes(),
        "feature_manifest_gate": {"status": "PASS"},
        "folds": _folds(final_holdout=final_holdout),
    }


def _contamination_audit(*, classification: str = phase5.EXPECTED_SPLIT_CLASSIFICATION) -> dict[str, object]:
    return {
        "stage": "wfa_split_contamination_audit",
        "status": phase5.EXPECTED_CONTAMINATION_STATUS,
        "summary": {
            "classification": classification,
            "failure_count": 0,
            "fold_count": 48,
            "market_year_count": 8,
            "model_trust_ready": False,
            "valid_for_independent_holdout_claims": False,
            "valid_for_same_fold_rolling_retraining_research_evidence": True,
            "warning_count": 2,
        },
        "warnings": [
            "embargo_and_later_fold_oos_reuse_classification: WARN_EXPECTED_ROLLING_RETRAINING_REUSE",
            "validation_window_presence: WARN_NO_INNER_VALIDATION_WINDOW",
        ],
        "failures": [],
    }


def _feature_manifest(output_hashes: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "feature_count": 114,
        "failure_count": 0,
        "warning_count": 0,
        "output_file_hashes": output_hashes or _feature_hashes(),
    }


def _feature_placement(output_hashes: dict[str, str] | None = None) -> dict[str, object]:
    hashes = output_hashes or _feature_hashes()
    return {
        "status": "PASS_ACTIVE_FEATURE_PLACEMENT_V2_CORE_NO_DOWNSTREAM",
        "records": [
            {
                "path": phase5.feature_matrix_path(market, year),
                "sha256": hashes[phase5.feature_matrix_path(market, year)],
                "active_matches_staged": True,
            }
            for market, year in phase5.expected_pairs()
        ],
        "failures": [],
    }


def _base_repo(
    tmp_path: Path,
    *,
    split_plan: dict[str, object] | None = None,
    contamination_audit: dict[str, object] | None = None,
    feature_manifest: dict[str, object] | None = None,
    feature_placement: dict[str, object] | None = None,
    phase4_payload: dict[str, object] | None = None,
    phase7_payload: dict[str, object] | None = None,
) -> Path:
    _write_text(tmp_path / "MASTER_AUDIT.md", "Phase 5 WFA split planning\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "Phase 5 split contamination research only\n")
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_text(tmp_path / phase5.MODELS_CONFIG, "purge_bars: 61\n")
    _write_json(tmp_path / phase5.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase5.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(
        tmp_path / phase5.DEFAULT_PHASE1B,
        _phase_payload("1b", "PASS_MASTER_AUDIT_PHASE1B_RECONCILIATION_REPORT_ONLY", "phase1b_master_audit_status"),
    )
    _write_json(
        tmp_path / phase5.DEFAULT_PHASE2,
        _phase_payload("2", "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY", "phase2_master_audit_status"),
    )
    _write_json(
        tmp_path / phase5.DEFAULT_PHASE3,
        _phase_payload("3", "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY", "phase3_master_audit_status"),
    )
    _write_json(tmp_path / phase5.DEFAULT_PHASE4, phase4_payload or _phase4_payload())
    _write_json(
        tmp_path / phase5.DEFAULT_PHASE6,
        _phase_payload("6", "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY", "phase6_master_audit_status"),
    )
    _write_json(tmp_path / phase5.DEFAULT_PHASE7, phase7_payload or _phase7_payload())
    _write_json(tmp_path / phase5.SPLIT_PLAN, split_plan or _split_plan())
    _write_json(tmp_path / phase5.CONTAMINATION_AUDIT, contamination_audit or _contamination_audit())
    _write_json(tmp_path / phase5.FEATURE_MANIFEST, feature_manifest or _feature_manifest())
    _write_json(tmp_path / phase5.FEATURE_PLACEMENT_HASHES, feature_placement or _feature_placement())
    return tmp_path / phase5.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    split_plan: dict[str, object] | None = None,
    contamination_audit: dict[str, object] | None = None,
    feature_manifest: dict[str, object] | None = None,
    feature_placement: dict[str, object] | None = None,
    phase4_payload: dict[str, object] | None = None,
    phase7_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(
        tmp_path,
        split_plan=split_plan,
        contamination_audit=contamination_audit,
        feature_manifest=feature_manifest,
        feature_placement=feature_placement,
        phase4_payload=phase4_payload,
        phase7_payload=phase7_payload,
    )
    return phase5.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[" M configs/models.yaml"],
    )


def test_phase5_reconciliation_passes_research_only_without_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase5.PASS_STATUS
    assert report["summary"]["phase5_master_audit_status"] == "RUN_ACCEPTED_LIMITED_WFA_SPLIT_CONTAMINATION_GUARD"
    assert report["summary"]["fold_count"] == 48
    assert report["summary"]["feature_hash_match_count"] == 8
    assert report["summary"]["placement_hash_match_count"] == 8
    assert report["summary"]["classification"] == phase5.EXPECTED_SPLIT_CLASSIFICATION
    assert report["summary"]["valid_for_independent_holdout_claims"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["hardened_split_candidate_consumed"] is False
    assert report["summary"]["models_config_caveat"]["git_status"] == "M"
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_feature_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_hashes = _feature_hashes()
    bad_hashes[phase5.feature_matrix_path("CL", 2024)] = "bad".ljust(64, "0")

    report = _build(tmp_path, split_plan=_split_plan(input_hashes=bad_hashes))

    assert report["status"] == phase5.FAIL_STATUS
    assert any("input hashes" in failure for failure in report["failures"])


def test_contamination_classification_change_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        contamination_audit=_contamination_audit(classification="independent_holdout_ready"),
    )

    assert report["status"] == phase5.FAIL_STATUS
    assert any("research-only" in failure for failure in report["failures"])


def test_final_holdout_fold_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, split_plan=_split_plan(final_holdout=True))

    assert report["status"] == phase5.FAIL_STATUS
    assert any("fold counts" in failure for failure in report["failures"])


def test_downstream_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, phase7_payload=_phase7_payload(promotion_allowed=True))

    assert report["status"] == phase5.FAIL_STATUS
    assert any("model trust, or promotion" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase5.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase5.REPORT_JSON,
        phase5.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase5.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase5_split_build_executed"] is False
    assert payload["non_approval"]["feature_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase5.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase5.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
