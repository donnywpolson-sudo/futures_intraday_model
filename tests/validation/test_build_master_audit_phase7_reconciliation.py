from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase7_reconciliation as phase7


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
                "audit_area": "Phase 7",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "evidence_state": "missing",
                "accepted_evidence": [],
                "scope": "post-WFA diagnostics/model selection audit not executed here",
                "notes": ["No bounded Phase 7 master audit artifact was accepted by this inventory."],
            }
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
        },
    }


def _artifact_payloads(tmp_path: Path) -> dict[str, dict[str, object]]:
    run = phase7.RUN_ID
    prediction_path = f"data/predictions/{run}/oos_predictions.parquet"
    prediction_hash = "107f537ff07e3f14279371501dc7642599ab55f96ec69cbbf697fd5031be494b"
    manifest_path = phase7.PREDICTIONS_MANIFEST.as_posix()
    manifest_payload: dict[str, object] = {
        "run": run,
        "prediction_count": 123,
        "duplicate_prediction_count": 0,
        "prediction_path": prediction_path,
        "prediction_artifact_written": True,
        "prediction_writes_enabled": True,
        "artifact_evidence_ready": True,
        "failure_count": 0,
        "warning_count": 0,
        "output_file_hashes": {prediction_path: prediction_hash},
        "input_file_hashes": {},
    }
    _write_json(tmp_path / phase7.PREDICTIONS_MANIFEST, manifest_payload)
    manifest_hash = phase7.inventory.sha256_file(tmp_path / phase7.PREDICTIONS_MANIFEST)
    prediction_audit_payload: dict[str, object] = {
        "status": "PASS",
        "phase7_prediction_audit_ready": True,
        "run": run,
        "prediction_path": prediction_path,
        "predictions_manifest_path": manifest_path,
        "prediction_count": 123,
        "target_count": 8,
        "failure_count": 0,
        "scope": {
            "markets": ["ES", "CL", "ZN", "6E"],
            "years": [2023, 2024],
            "prediction_markets": ["6E", "CL", "ES", "ZN"],
            "prediction_years": [2024],
            "fold_count": 48,
            "prediction_count": 123,
        },
        "input_file_hashes": {
            prediction_path: prediction_hash,
            manifest_path: manifest_hash,
        },
    }
    wfa_report_payload: dict[str, object] = {
        "run": run,
        "fold_count": 48,
        "prediction_count": 123,
        "duplicate_prediction_count": 0,
        "prediction_artifact_written": True,
        "prediction_writes_enabled": True,
        "artifact_evidence_ready": True,
        "failure_count": 0,
        "warning_count": 0,
    }
    prediction_diagnostics_payload: dict[str, object] = {
        "status": "PREDICTION_DIAGNOSTICS_READY",
        "run": run,
        "prediction_count": 123,
        "target_count": 8,
        "failure_count": 0,
        "failure_labels": ["weak_signal"],
    }
    failure_analysis_payload: dict[str, object] = {
        "status": "PASS",
        "run": run,
        "prediction_count": 123,
        "policy_row_count": 12,
        "failure_count": 0,
        "model_promotion_allowed": False,
        "failure_classifications": [
            {"classification": "gross_edge_absent", "severity": "Severe"},
            {"classification": "baseline_failure", "severity": "Severe"},
        ],
    }
    statistical_validity_payload: dict[str, object] = {
        "status": "FAIL",
        "run": run,
        "prediction_count": 123,
        "policy_trade_count": 4,
        "failure_count": 5,
        "model_promotion_allowed": False,
    }
    phase8_payload: dict[str, object] = {
        "run": run,
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "final_holdout_touched": False,
        "used_final_holdout_for_tuning": False,
        "promotion_metric_gate": {"status": "FAIL", "failure_count": 25},
        "statistical_validity_gate": {"status": "FAIL", "failure_count": 7},
    }
    return {
        "prediction_audit": prediction_audit_payload,
        "manifest": manifest_payload,
        "wfa_report": wfa_report_payload,
        "prediction_diagnostics": prediction_diagnostics_payload,
        "failure_analysis": failure_analysis_payload,
        "statistical_validity": statistical_validity_payload,
        "phase8": phase8_payload,
    }


def _base_repo(tmp_path: Path, payload_overrides: dict[str, dict[str, object]] | None = None) -> dict[str, Path]:
    for name in ("MASTER_AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"):
        _write_text(tmp_path / name)
    _write_json(tmp_path / phase7.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase7.DEFAULT_OVERVIEW, _overview_payload())
    payloads = _artifact_payloads(tmp_path)
    if payload_overrides:
        for key, override in payload_overrides.items():
            payloads[key] = override
    _write_json(tmp_path / phase7.PREDICTION_AUDIT, payloads["prediction_audit"])
    _write_json(tmp_path / phase7.WFA_REPORT, payloads["wfa_report"])
    _write_json(tmp_path / phase7.PREDICTION_DIAGNOSTICS, payloads["prediction_diagnostics"])
    _write_json(tmp_path / phase7.FAILURE_ANALYSIS, payloads["failure_analysis"])
    _write_json(tmp_path / phase7.STATISTICAL_VALIDITY, payloads["statistical_validity"])
    _write_json(tmp_path / phase7.PHASE8_DECISION, payloads["phase8"])
    return {"reports_root": tmp_path / phase7.DEFAULT_REPORTS_ROOT}


def _build(tmp_path: Path, payload_overrides: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    paths = _base_repo(tmp_path, payload_overrides=payload_overrides)
    return phase7.build_report(
        repo_root=tmp_path,
        reports_root=paths["reports_root"],
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase7_reconciliation_passes_without_prediction_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase7.PASS_STATUS
    assert report["summary"]["phase7_master_audit_status"] == "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION"
    assert report["summary"]["prediction_parquet_read_executed"] is False
    assert report["summary"]["prediction_count"] == 123
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert not (tmp_path / f"data/predictions/{phase7.RUN_ID}/oos_predictions.parquet").exists()


def test_statistical_failure_is_preserved_as_blocker_not_report_failure(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase7.PASS_STATUS
    assert any(
        item["finding_id"] == "phase7-003-economic-and-statistical-blockers-remain"
        for item in report["findings"]
    )
    blocker_check = next(item for item in report["checks"] if item["name"] == "downstream_diagnostics_preserve_blockers")
    assert blocker_check["status"] == "PASS"


def test_prediction_audit_not_pass_fails_closed(tmp_path: Path) -> None:
    payloads = _artifact_payloads(tmp_path)
    bad_audit = copy.deepcopy(payloads["prediction_audit"])
    bad_audit["status"] = "FAIL"

    report = _build(tmp_path, {"prediction_audit": bad_audit})

    assert report["status"] == phase7.FAIL_STATUS
    assert any("public Phase 7 prediction audit" in failure for failure in report["failures"])


def test_json_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    payloads = _artifact_payloads(tmp_path)
    bad_audit = copy.deepcopy(payloads["prediction_audit"])
    bad_audit["input_file_hashes"][phase7.PREDICTIONS_MANIFEST.as_posix()] = "bad-hash"

    report = _build(tmp_path, {"prediction_audit": bad_audit})

    assert report["status"] == phase7.FAIL_STATUS
    assert any("hashes do not reconcile" in failure for failure in report["failures"])


def test_phase8_promotion_true_fails_closed(tmp_path: Path) -> None:
    payloads = _artifact_payloads(tmp_path)
    bad_phase8 = copy.deepcopy(payloads["phase8"])
    bad_phase8["promoted"] = True

    report = _build(tmp_path, {"phase8": bad_phase8})

    assert report["status"] == phase7.FAIL_STATUS
    assert any("non-approval flags" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)

    exit_code = phase7.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(paths["reports_root"]),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in paths["reports_root"].iterdir()) == [
        phase7.REPORT_JSON,
        phase7.REPORT_MD,
    ]
    payload = json.loads((paths["reports_root"] / phase7.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["prediction_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase7.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase7.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
