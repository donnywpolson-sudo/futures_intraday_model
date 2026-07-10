from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase4_reconciliation as phase4


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _hash(market: str, year: int, prefix: str) -> str:
    return f"{prefix}-{market}-{year}".ljust(64, "0")[:64]


def _active_label_hashes() -> dict[str, str]:
    return {
        phase4.active_label_path(market, year): _hash(market, year, "label")
        for market, year in phase4.expected_pairs()
    }


def _feature_hashes() -> dict[str, str]:
    return {
        phase4.feature_matrix_path(market, year): _hash(market, year, "feature")
        for market, year in phase4.expected_pairs()
    }


def _row_count(market: str, year: int) -> int:
    return 1000 + (phase4.EXPECTED_MARKETS.index(market) * 10) + (year - 2023)


def _feature_cols(extra: list[str] | None = None) -> list[str]:
    return [f"feature_fixture_{idx}" for idx in range(phase4.EXPECTED_FEATURE_COUNT)] + (extra or [])


def _target_cols(extra: list[str] | None = None) -> list[str]:
    return [f"target_fixture_{idx}" for idx in range(phase4.EXPECTED_TARGET_COUNT)] + (extra or [])


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
                "audit_area": "Phase 4",
                "run_status": "RUN",
                "detail_status": "RUN_LIMITED_SCOPE_FEATURE_LEAKAGE_EVIDENCE",
                "evidence_state": "limited-scope",
                "scope": "active v2 Tier 1 core feature matrix leakage, 6E/CL/ES/ZN, 2023/2024",
                "accepted_evidence": [],
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
            "model_trust_ready": False,
        },
    }


def _phase2_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE2_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase2_master_audit_status": "RUN_LIMITED_SCOPE_PHASE2_ACTIVE_CAUSAL_HASH_LINEAGE_RECONCILIATION",
            "phase2_full_master_audit_accepted": False,
            "model_trust_ready": False,
        },
    }


def _phase3_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE3_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase3_master_audit_status": "RUN_LIMITED_SCOPE_PHASE3_ACTIVE_LABEL_TIMING_HASH_LINEAGE_RECONCILIATION",
            "phase3_limited_label_timing_hash_lineage_ready": True,
            "phase3_full_master_audit_accepted": False,
            "active_feature_hash_match_count": 8,
            "target_feature_intersection_count": 0,
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
            "promotion_allowed": False,
        },
    }


def _active_label_manifest() -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/causally_gated_normalized",
        "output_root": "data/labeled",
        "markets": list(phase4.EXPECTED_MARKETS),
        "years": list(phase4.EXPECTED_YEARS),
        "failure_count": 0,
        "warning_count": 0,
        "output_file_hashes": _active_label_hashes(),
        "outputs": [
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "output_path": phase4.active_label_path(market, year),
                "output_rows": _row_count(market, year),
                "target_valid_rows": _row_count(market, year) - 10,
                "target_invalid_rows": 10,
            }
            for market, year in phase4.expected_pairs()
        ],
    }


def _feature_audit_records(feature_cols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "availability_timestamp": "feature row timestamp `ts`; no future rows allowed",
            "drift_decay_check_status": "registered_for_pre_promotion_review; Phase 8/9 promotion requires stability evidence",
            "economic_rationale": "Fixture rationale.",
            "family": "fixture",
            "feature": feature,
            "leakage_risk": "low",
            "lookback_window": "current row plus trailing rows",
            "source_column_artifact": "Phase 3 labeled parquet derived from Phase 2 inputs",
            "train_only_transform_status": "Phase 4 uses deterministic causal transforms only; fitted transforms must occur inside downstream train folds",
        }
        for feature in feature_cols
    ]


def _feature_manifest(
    *,
    input_hashes: dict[str, str] | None = None,
    output_hashes: dict[str, str] | None = None,
    feature_cols: list[str] | None = None,
    target_cols: list[str] | None = None,
    feature_audit: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    features = feature_cols or _feature_cols()
    targets = target_cols or _target_cols()
    audit = feature_audit if feature_audit is not None else _feature_audit_records(features)
    return {
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/labeled",
        "output_root": "data/feature_matrices",
        "markets": list(phase4.EXPECTED_MARKETS),
        "years": list(phase4.EXPECTED_YEARS),
        "failure_count": 0,
        "warning_count": 0,
        "feature_count": 114,
        "input_file_hashes": input_hashes or _active_label_hashes(),
        "output_file_hashes": output_hashes or _feature_hashes(),
        "label_manifest_gate": {
            "status": "PASS",
            "manifest_path": phase4.ACTIVE_LABEL_MANIFEST.as_posix(),
        },
        "feature_audit_gate": {
            "status": "PASS",
            "feature_count": 114,
            "audit_record_count": 114,
            "failure_count": 0,
            "failures": [],
            "required_fields": list(phase4.REQUIRED_FEATURE_AUDIT_FIELDS),
        },
        "forbidden_feature_leakage_failures": [],
        "outputs": [
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "input_path": phase4.active_label_path(market, year),
                "output_path": phase4.feature_matrix_path(market, year),
                "input_rows": _row_count(market, year),
                "output_rows": _row_count(market, year),
                "feature_count": 114,
                "training_row_valid_rows": _row_count(market, year) - 10,
                "target_valid_rows": _row_count(market, year) - 10,
            }
            for market, year in phase4.expected_pairs()
        ],
        "registry": {
            "excluded_cols": [],
            "feature_audit": audit,
            "feature_audit_gate": {"status": "PASS"},
            "feature_cols": features,
            "feature_families": {},
            "metadata_cols": [],
            "target_cols": targets,
        },
    }


def _active_feature_placement(output_hashes: dict[str, str] | None = None) -> dict[str, object]:
    hashes = output_hashes or _feature_hashes()
    records: list[dict[str, object]] = []
    for market, year in phase4.expected_pairs():
        path = phase4.feature_matrix_path(market, year)
        digest = hashes[path]
        records.append(
            {
                "name": f"{market}:{year}",
                "path": path,
                "rows": _row_count(market, year),
                "columns": phase4.EXPECTED_FEATURE_MATRIX_COLUMNS,
                "sha256": digest,
                "staged_sha256": digest,
                "backup_sha256": "backup".ljust(64, "0"),
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            }
        )
    records.extend(
        [
            {
                "name": "feature_cols.json",
                "path": "data/feature_matrices/feature_cols.json",
                "sha256": "a" * 64,
                "staged_sha256": "a" * 64,
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            },
            {
                "name": "target_cols.json",
                "path": "data/feature_matrices/target_cols.json",
                "sha256": "b" * 64,
                "staged_sha256": "b" * 64,
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            },
            {
                "name": "feature_manifest.json",
                "path": phase4.FEATURE_MANIFEST.as_posix(),
                "sha256": "c" * 64,
                "staged_sha256": "c" * 64,
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            },
            {
                "name": "registry.json",
                "path": "reports/features_baseline/registry.json",
                "sha256": "d" * 64,
                "staged_sha256": "d" * 64,
                "active_matches_staged": True,
                "backup_matches_pre_active": True,
            },
        ]
    )
    return {
        "status": phase4.EXPECTED_FEATURE_PLACEMENT_STATUS,
        "failures": [],
        "records": records,
    }


def _feature_leakage_audit(
    *,
    diagnostic_only: bool = True,
    required_feature_removals: list[str] | None = None,
) -> dict[str, object]:
    return {
        "status": "PASS",
        "verdict": phase4.EXPECTED_LEAKAGE_VERDICT,
        "diagnostic_only": diagnostic_only,
        "feature_count": 114,
        "target_column_count": 97,
        "required_feature_removals": required_feature_removals or [],
        "confidence_score": {
            "score": 96,
            "deductions": [
                {"points": 2, "reason": phase4.EXPECTED_LEAKAGE_DEDUCTIONS[0]},
                {"points": 2, "reason": phase4.EXPECTED_LEAKAGE_DEDUCTIONS[1]},
            ],
        },
        "summary_counts": {
            "matrix_file_status_counts": {"PASS": 8},
            "leakage_finding_status_counts": {"PASS": 5, "WARN": 1},
            "embedding_finding_severity_counts": {"WARN": 132},
            "feature_risk_class_counts": {"low": 71, "medium": 43},
        },
        "non_approval": {
            "artifact_freeze": False,
            "cleanup": False,
            "feature_rebuild": False,
            "final_holdout": False,
            "paper_live": False,
            "phase8": False,
            "prediction_generation": False,
            "promotion": False,
            "provider_downloads": False,
            "staging_commit_push": False,
            "wfa_modeling": False,
        },
    }


def _base_repo(
    tmp_path: Path,
    *,
    feature_manifest: dict[str, object] | None = None,
    active_feature_placement: dict[str, object] | None = None,
    leakage_audit: dict[str, object] | None = None,
    feature_cols: list[str] | None = None,
    target_cols: list[str] | None = None,
) -> Path:
    _write_text(tmp_path / "MASTER_AUDIT.md", "Phase 4 Feature Matrix Feature Lineage Target Leakage\n")
    _write_text(tmp_path / "PROJECT_OUTLINE.md", "Phase 4 feature audit gate feature_cols target_cols\n")
    _write_text(tmp_path / "CODEX_HANDOFF.md", "handoff\n")
    _write_json(tmp_path / phase4.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase4.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(tmp_path / phase4.DEFAULT_PHASE1B, _phase1b_payload())
    _write_json(tmp_path / phase4.DEFAULT_PHASE2, _phase2_payload())
    _write_json(tmp_path / phase4.DEFAULT_PHASE3, _phase3_payload())
    _write_json(tmp_path / phase4.DEFAULT_PHASE6, _phase6_payload())
    _write_json(tmp_path / phase4.DEFAULT_PHASE7, _phase7_payload())
    _write_json(tmp_path / phase4.ACTIVE_LABEL_MANIFEST, _active_label_manifest())
    features = feature_cols or _feature_cols()
    targets = target_cols or _target_cols()
    _write_json(
        tmp_path / phase4.FEATURE_MANIFEST,
        feature_manifest or _feature_manifest(feature_cols=features, target_cols=targets),
    )
    _write_json(
        tmp_path / phase4.ACTIVE_FEATURE_PLACEMENT,
        active_feature_placement or _active_feature_placement(),
    )
    _write_json(tmp_path / phase4.FEATURE_LEAKAGE_AUDIT, leakage_audit or _feature_leakage_audit())
    _write_json(tmp_path / phase4.FEATURE_COLS, features)
    _write_json(tmp_path / phase4.TARGET_COLS, targets)
    return tmp_path / phase4.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    feature_manifest: dict[str, object] | None = None,
    active_feature_placement: dict[str, object] | None = None,
    leakage_audit: dict[str, object] | None = None,
    feature_cols: list[str] | None = None,
    target_cols: list[str] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(
        tmp_path,
        feature_manifest=feature_manifest,
        active_feature_placement=active_feature_placement,
        leakage_audit=leakage_audit,
        feature_cols=feature_cols,
        target_cols=target_cols,
    )
    return phase4.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase4_reconciliation_passes_limited_feature_leakage_lineage_without_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase4.PASS_STATUS
    assert (
        report["summary"]["phase4_master_audit_status"]
        == "RUN_LIMITED_SCOPE_PHASE4_ACTIVE_FEATURE_LEAKAGE_HASH_LINEAGE_RECONCILIATION"
    )
    assert report["summary"]["active_feature_hash_match_count"] == 8
    assert report["summary"]["feature_hash_match_count"] == 8
    assert report["summary"]["row_count_match_count"] == 8
    assert report["summary"]["feature_count"] == 114
    assert report["summary"]["target_count"] == 97
    assert report["summary"]["target_feature_intersection_count"] == 0
    assert report["summary"]["required_feature_removals_count"] == 0
    assert report["summary"]["phase4_full_master_audit_accepted"] is False
    assert report["summary"]["feature_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_feature_placement_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    bad_hashes = _feature_hashes()
    bad_hashes[phase4.feature_matrix_path("CL", 2024)] = "bad".ljust(64, "0")

    report = _build(tmp_path, active_feature_placement=_active_feature_placement(bad_hashes))

    assert report["status"] == phase4.FAIL_STATUS
    assert any("placement hashes" in failure for failure in report["failures"])


def test_target_feature_registry_intersection_fails_closed(tmp_path: Path) -> None:
    features = _feature_cols()
    targets = _target_cols()
    features[0] = targets[0]
    manifest = _feature_manifest(feature_cols=features, target_cols=targets)

    report = _build(tmp_path, feature_manifest=manifest, feature_cols=features, target_cols=targets)

    assert report["status"] == phase4.FAIL_STATUS
    assert any("registry boundary" in failure for failure in report["failures"])


def test_missing_feature_audit_field_fails_closed(tmp_path: Path) -> None:
    features = _feature_cols()
    audit = _feature_audit_records(features)
    audit[0] = copy.deepcopy(audit[0])
    audit[0].pop("availability_timestamp")
    manifest = _feature_manifest(feature_cols=features, feature_audit=audit)

    report = _build(tmp_path, feature_manifest=manifest, feature_cols=features)

    assert report["status"] == phase4.FAIL_STATUS
    assert any("feature audit records" in failure for failure in report["failures"])


def test_leakage_diagnostic_limitation_change_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, leakage_audit=_feature_leakage_audit(diagnostic_only=False))

    assert report["status"] == phase4.FAIL_STATUS
    assert any("diagnostic-only" in failure for failure in report["failures"])


def test_required_feature_removal_fails_closed(tmp_path: Path) -> None:
    report = _build(
        tmp_path,
        leakage_audit=_feature_leakage_audit(required_feature_removals=["feature_fixture_0"]),
    )

    assert report["status"] == phase4.FAIL_STATUS
    assert any("feature leakage audit" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase4.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase4.REPORT_JSON,
        phase4.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase4.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase4_feature_build_executed"] is False
    assert payload["non_approval"]["feature_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase4.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase4.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
