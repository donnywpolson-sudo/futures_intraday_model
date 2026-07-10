from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase6_reconciliation as phase6


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
                "audit_area": "Phase 6",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_PHASE6_MASTER_AUDIT_NOT_ACCEPTED",
                "evidence_state": "unknown",
                "accepted_evidence": [],
                "scope": "phase6 WFA/modeling audit not executed here",
                "notes": ["WFA/modeling and predictions are forbidden in this scope."],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
        "summary": {"failure_count": 0},
    }


def _phase7_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase7_master_audit_status": "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
            "prediction_parquet_read_executed": False,
        },
    }


def _model_risk_gate() -> dict[str, object]:
    return {
        "gate_name": "model_risk_gate",
        "status": "PASS_METADATA_READY",
        "model_risk_metadata_ready": True,
        "model_trust_ready": False,
        "model_trust_blockers": [
            "feature-importance stability is registered for pre-promotion review"
        ],
        "failure_count": 0,
        "failures": [],
        "hyperparameter_budget": {
            "hyperparameter_tuning_allowed_initially": False,
            "budget": "fixed baseline controls only",
        },
        "seed_policy": {
            "random_splits_allowed": False,
            "determinism_source": "chronological split plan",
        },
        "calibration": {
            "calibration_id": "no_calibration",
            "test_fold_fit_allowed": False,
            "final_holdout_fit_allowed": False,
            "method": "no calibration fit",
        },
        "class_imbalance_handling": {
            "class_counts_recorded_per_fold": True,
            "dummy_fallback_count": 0,
        },
        "model_ids": [
            "ridge_return_v1",
            "logistic_direction_v1",
            "logistic_fade_success_v1",
            "logistic_trend_danger_v1",
            "logistic_trend_adverse_long_v1",
            "logistic_trend_favorable_long_v1",
            "logistic_trend_adverse_short_v1",
            "logistic_trend_favorable_short_v1",
        ],
    }


def _phase6_payloads() -> dict[str, dict[str, object]]:
    run = phase6.RUN_ID
    model_ids = [
        "ridge_return_v1",
        "logistic_direction_v1",
        "logistic_fade_success_v1",
        "logistic_trend_danger_v1",
        "logistic_trend_adverse_long_v1",
        "logistic_trend_favorable_long_v1",
        "logistic_trend_adverse_short_v1",
        "logistic_trend_favorable_short_v1",
    ]
    target_names = [
        "target_ret_30m",
        "target_sign_with_deadzone",
        "target_accept_any_30m",
        "target_apex_dll_eod_threat_30m",
        "target_apex_dll_eod_threat_long_30m",
        "target_favorable_after_cost_long_30m",
        "target_apex_dll_eod_threat_short_30m",
        "target_favorable_after_cost_short_30m",
    ]
    common = {
        "run": run,
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES", "CL", "ZN", "6E"],
        "years": [2023, 2024],
        "prediction_markets": ["6E", "CL", "ES", "ZN"],
        "prediction_years": [2024],
        "fold_count": 48,
        "unfiltered_selectable_fold_count": 48,
        "prediction_count": 123,
        "duplicate_prediction_count": 0,
        "prediction_writes_enabled": False,
        "prediction_artifact_written": False,
        "prediction_artifact_write_skipped": True,
        "prediction_path": None,
        "output_root": None,
        "predictions_root": None,
        "artifact_evidence_ready": True,
        "artifact_evidence_failures": [],
        "failure_count": 0,
        "warning_count": 0,
        "model_risk_gate": _model_risk_gate(),
    }
    input_file_hashes = {
        "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json": "a" * 64,
        phase6.FEATURE_SET.as_posix(): "b" * 64,
        "configs/models.yaml": "c" * 64,
    }
    for market in ("6E", "CL", "ES", "ZN"):
        for year in (2023, 2024):
            input_file_hashes[f"data/feature_matrices/{market}/{year}.parquet"] = "d" * 64
    manifest = {
        **common,
        "model_ids": model_ids,
        "target_names": target_names,
        "input_file_hashes": input_file_hashes,
        "output_file_hashes": {},
    }
    wfa_report = {
        **common,
        "models": [{"model_id": model_id} for model_id in model_ids],
    }
    preflight = {
        "status": "PASS_PHASE6_WFA_RUNNER_PREFLIGHT_READY_REPORT_ONLY",
        "summary": {
            "commands_executed": 0,
            "failure_count": 0,
            "warning_count": 0,
            "feature_count": 114,
            "feature_file_count": 8,
            "fold_count": 48,
            "model_count": 8,
            "model_training_performed": False,
            "prediction_generation_performed": False,
            "prediction_file_count": 0,
            "total_prediction_file_count": 1,
        },
        "scope": {
            "feature_root": "data/feature_matrices",
            "market_year_count": 8,
            "markets": ["6E", "CL", "ES", "ZN"],
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "split_plan": "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core/split_plan.json",
            "years": [2023, 2024],
        },
    }
    return {
        "preflight": preflight,
        "feature_set": {"feature_count": 114, "features": ["feature_1"]},
        "wfa_report": wfa_report,
        "manifest": manifest,
    }


def _base_repo(tmp_path: Path, payload_overrides: dict[str, dict[str, object]] | None = None) -> dict[str, Path]:
    for name in ("MASTER_AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"):
        _write_text(tmp_path / name)
    _write_json(tmp_path / phase6.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase6.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(tmp_path / phase6.DEFAULT_PHASE7, _phase7_payload())
    payloads = _phase6_payloads()
    if payload_overrides:
        for key, override in payload_overrides.items():
            payloads[key] = override
    _write_json(tmp_path / phase6.PREFLIGHT_REPORT, payloads["preflight"])
    _write_json(tmp_path / phase6.FEATURE_SET, payloads["feature_set"])
    _write_json(tmp_path / phase6.WFA_REPORT, payloads["wfa_report"])
    _write_json(tmp_path / phase6.PREDICTIONS_MANIFEST, payloads["manifest"])
    return {"reports_root": tmp_path / phase6.DEFAULT_REPORTS_ROOT}


def _build(tmp_path: Path, payload_overrides: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    paths = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return phase6.build_report(
        repo_root=tmp_path,
        reports_root=paths["reports_root"],
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase6_reconciliation_passes_without_parquet_artifacts(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase6.PASS_STATUS
    assert report["summary"]["phase6_master_audit_status"] == "RUN_LIMITED_SCOPE_PHASE6_REPORT_ONLY_WFA_RECONCILIATION"
    assert report["summary"]["prediction_count"] == 123
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["prediction_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_prediction_artifact_written_fails_closed(tmp_path: Path) -> None:
    payloads = _phase6_payloads()
    bad_manifest = copy.deepcopy(payloads["manifest"])
    bad_manifest["prediction_artifact_written"] = True

    report = _build(tmp_path, {"manifest": bad_manifest})

    assert report["status"] == phase6.FAIL_STATUS
    assert any("prediction writes" in failure for failure in report["failures"])


def test_manifest_wfa_count_mismatch_fails_closed(tmp_path: Path) -> None:
    payloads = _phase6_payloads()
    bad_report = copy.deepcopy(payloads["wfa_report"])
    bad_report["prediction_count"] = 999

    report = _build(tmp_path, {"wfa_report": bad_report})

    assert report["status"] == phase6.FAIL_STATUS
    assert any("counts" in failure for failure in report["failures"])


def test_model_trust_true_fails_closed(tmp_path: Path) -> None:
    payloads = _phase6_payloads()
    bad_manifest = copy.deepcopy(payloads["manifest"])
    bad_manifest["model_risk_gate"]["model_trust_ready"] = True

    report = _build(tmp_path, {"manifest": bad_manifest})

    assert report["status"] == phase6.FAIL_STATUS
    assert any("model-risk" in failure for failure in report["failures"])


def test_preflight_execution_count_fails_closed(tmp_path: Path) -> None:
    payloads = _phase6_payloads()
    bad_preflight = copy.deepcopy(payloads["preflight"])
    bad_preflight["summary"]["commands_executed"] = 1

    report = _build(tmp_path, {"preflight": bad_preflight})

    assert report["status"] == phase6.FAIL_STATUS
    assert any("preflight" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)

    exit_code = phase6.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(paths["reports_root"]),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in paths["reports_root"].iterdir()) == [
        phase6.REPORT_JSON,
        phase6.REPORT_MD,
    ]
    payload = json.loads((paths["reports_root"] / phase6.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["wfa_modeling_executed"] is False
    assert payload["non_approval"]["hardened_split_candidate_consumed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase6.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase6.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
