from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_trial_search_ledger_schema_remediation_plan as plan,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _upstream() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_TRIAL_LEDGER_SEARCH_PATH_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "trial_ledger_search_path_complete": False,
            "pbo_status": "FAIL_MISSING_TRIAL_LOG",
            "deflated_sharpe_status": "FAIL_MISSING_TRIAL_LOG",
            "multiple_testing_status": "FAIL_MISSING_TRIAL_LOG",
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _experiment_rows() -> list[dict[str, object]]:
    return [
        {
            "audit_report_path": f"reports/experiments/audit_{idx}.json",
            "command": "existing saved WFA/report run",
            "configs": ["configs/costs.yaml", "configs/models.yaml"],
            "net_return_dollars": -100.0 * idx,
            "gross_return_dollars": -50.0 * idx,
            "passed": False,
            "pass_fail_reason": ["base_net_nonpositive"],
            "profile": "tier_1",
            "robustness_status": "FAIL",
            "timestamp": f"2026-07-0{idx}T00:00:00+00:00",
            "trades": idx,
        }
        for idx in range(1, 5)
    ]


def _source_report_paths() -> list[str]:
    base = "reports/pipeline_audit/hypothesis_{idx:02d}_source_packet.json"
    paths = [base.format(idx=idx) for idx in range(17)]
    paths.extend(
        [
            "reports/pipeline_audit/hypothesis_00_confirmation_packet.json",
            "reports/pipeline_audit/hypothesis_01_locked_packet.json",
            "reports/pipeline_audit/hypothesis_02_extra_packet.json",
            "reports/pipeline_audit/hypothesis_03_extra_packet.json",
        ]
    )
    assert len(paths) == 21
    return paths


def _registry() -> dict[str, object]:
    paths = _source_report_paths()
    hypotheses: list[dict[str, object]] = []
    cursor = 0
    for idx in range(17):
        source_reports = [paths[cursor], paths[cursor].replace(".json", ".md")]
        cursor += 1
        if idx < 4:
            source_reports.extend([paths[17 + idx], paths[17 + idx].replace(".json", ".md")])
        hypotheses.append(
            {
                "target_hypothesis_id": f"h{idx:02d}",
                "status": "FROZEN" if idx == 0 else "REJECTED",
                "wfa_allowed": idx == 0,
                "source_reports": source_reports,
                "next_allowed_actions": [],
            }
        )
    return {"schema_version": 1, "hypotheses": hypotheses}


def _trial_status_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "trial_id": f"h{idx:02d}_candidate",
            "hypothesis_id": f"h{idx:02d}",
            "stage": "register_candidate",
            "status": "CANDIDATE",
            "evidence": [],
            "notes": "registered",
        }
        for idx in range(10)
    ]
    paths = _source_report_paths()
    rows.extend(
        {
            "trial_id": f"h{idx:02d}_terminal",
            "hypothesis_id": f"h{idx:02d}",
            "stage": "phase9_discovery_smoke",
            "status": "FROZEN" if idx == 0 else "REJECTED",
            "evidence": [paths[idx]],
            "notes": "terminal status",
        }
        for idx in range(12)
    )
    assert len(rows) == 22
    return rows


def _source_report(hypothesis_id: str, idx: int) -> dict[str, object]:
    return {
        "run": f"{hypothesis_id}_source_packet",
        "hypothesis_id": hypothesis_id,
        "created_at_utc": "2026-07-10T00:00:00+00:00",
        "git_commit": "abc123",
        "stage": "discovery",
        "evaluation_mode": "directional_net",
        "not_wfa": True,
        "not_phase8": True,
        "uses_saved_predictions": False,
        "scope": {"profile": "tier_1", "markets": ["ES"], "years": [2023, 2024]},
        "input_hashes": {
            "configs/costs.yaml": "costhash",
            "configs/models.yaml": "modelhash",
            f"data/feature_matrices/ES/202{idx % 2 + 3}.parquet": "datahash",
        },
        "input_paths": {"feature_cols": "data/feature_matrices/feature_cols.json"},
        "label_definition": {"threshold": "fixed threshold", "entry": "next open"},
        "target_columns": [f"target_{hypothesis_id}"],
        "model": {"family": "ridge_regression", "alpha": 1.0},
        "top_fraction": 0.05,
        "stage_summary": {
            "top_total_net_dollars": -10.0,
            "positive_top_net_fold_count": 0,
        },
        "event_count": 10,
        "failure_count": 0,
        "decision": "STOP_CLASS_COLLAPSE",
        "gates": [{"gate": "no_class_collapse", "pass": False}],
    }


def _wfa_report() -> dict[str, object]:
    return {
        "run": "tier1_core_phase6_full_predictions_20260706",
        "profile": "tier_1_core",
        "matrix": "baseline",
        "markets": ["ES", "CL", "ZN", "6E"],
        "years": [2023, 2024],
        "fold_count": 48,
        "prediction_count": 9_172_416,
        "models": [
            {
                "model_id": "ridge_return_v1",
                "family": "ridge_regression",
                "target": "target_ret_15m",
                "config_hash": "cfg1",
            },
            {
                "model_id": "logistic_direction_v1",
                "family": "logistic_regression",
                "target": "target_sign_with_deadzone",
                "config_hash": "cfg2",
            },
        ],
    }


def _predictions_manifest() -> dict[str, object]:
    return {
        "run": "tier1_core_phase6_full_predictions_20260706",
        "prediction_count": 9_172_416,
        "prediction_artifact_written": True,
        "prediction_path": "data/predictions/run/oos_predictions.parquet",
        "model_config_hash": "model_config_hash",
        "feature_config_hash": "feature_config_hash",
        "profile_config_hash": "profile_config_hash",
        "split_plan_config_hash": "split_plan_config_hash",
        "input_file_hashes": {"data/feature_matrices/ES/2024.parquet": "inputhash"},
        "output_file_hashes": {"data/predictions/run/oos_predictions.parquet": "predhash"},
        "model_risk_gate": {
            "model_families": ["ridge_regression", "logistic_regression"],
            "model_ids": ["ridge_return_v1", "logistic_direction_v1"],
            "seed_policy": {"random_splits_allowed": False},
            "hyperparameter_budget": {"budget": "fixed controls only"},
        },
    }


def _phase8_metrics() -> dict[str, object]:
    return {
        "run": "tier1_core_phase6_full_predictions_20260706",
        "metrics": {
            "overall": {
                "net_return_dollars": -55_995.215,
                "gross_return_dollars": -19_871.875,
                "cost_dollars": 36_123.34,
                "trade_count": 1_347,
            }
        },
    }


def _phase8_promotion() -> dict[str, object]:
    return {
        "run": "tier1_core_phase6_full_predictions_20260706",
        "promoted": False,
        "research_alpha_ready": False,
        "model_promotion_allowed": False,
        "promotion_gate": {
            "gate_config": {"min_net_return_dollars": 1.0},
            "promotion_blockers": ["statistical-validity evidence missing"],
        },
        "promotion_metric_gate": {"status": "FAIL"},
    }


def _statistical_summary() -> dict[str, object]:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "policy_trade_count": 1_347,
        "required_checks": {
            "pbo": {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None},
            "deflated_sharpe": {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None},
            "multiple_testing_adjustment": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
        },
    }


def _alpha_gap_matrix() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "alpha_evidence_ready": False,
        "buckets": [
            {"bucket_id": "statistical_pbo", "status": "MISSING_EVIDENCE"},
            {"bucket_id": "statistical_deflated_sharpe", "status": "MISSING_EVIDENCE"},
            {"bucket_id": "statistical_multiple_testing", "status": "MISSING_EVIDENCE"},
        ],
    }


def _closeout() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "bucket_dispositions": [
            {
                "bucket_id": "statistical_pbo",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "statistical_deflated_sharpe",
                "closeout_classification": "missing_required_evidence",
            },
            {
                "bucket_id": "statistical_multiple_testing",
                "closeout_classification": "missing_required_evidence",
            },
        ],
    }


def _run_status() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "data_model_commands_executed": False,
            "wfa_modeling_executed": False,
            "predictions_executed": False,
            "provider_network_calls_executed": False,
            "promotion_or_freeze_or_holdout_executed": False,
            "paper_or_live_executed": False,
        },
    }


def _base_repo(
    tmp_path: Path,
    *,
    upstream: dict[str, object] | None = None,
    experiment_rows: list[dict[str, object]] | None = None,
    registry: dict[str, object] | None = None,
    trial_status_rows: list[dict[str, object]] | None = None,
    phase8_promotion: dict[str, object] | None = None,
    statistical_summary: dict[str, object] | None = None,
) -> Path:
    _write_json(tmp_path / plan.UPSTREAM_RECONCILIATION, upstream or _upstream())
    _write_jsonl(tmp_path / plan.EXPERIMENT_LEDGER, experiment_rows or _experiment_rows())
    _write_json(tmp_path / plan.TARGET_REGISTRY, registry or _registry())
    _write_jsonl(
        tmp_path / plan.TARGET_TRIAL_STATUSES,
        trial_status_rows or _trial_status_rows(),
    )
    for idx, path in enumerate(_source_report_paths()[:7]):
        _write_json(tmp_path / path, _source_report(f"h{idx:02d}", idx))
        _write_text(tmp_path / path.replace(".json", ".md"), "source report\n")
    _write_json(tmp_path / plan.WFA_REPORT, _wfa_report())
    _write_json(tmp_path / plan.PREDICTIONS_MANIFEST, _predictions_manifest())
    _write_json(tmp_path / plan.PHASE8_METRICS, _phase8_metrics())
    _write_json(tmp_path / plan.PHASE8_PROMOTION, phase8_promotion or _phase8_promotion())
    _write_json(
        tmp_path / plan.STATISTICAL_SUMMARY,
        statistical_summary or _statistical_summary(),
    )
    _write_json(tmp_path / plan.ALPHA_GAP_MATRIX, _alpha_gap_matrix())
    _write_json(tmp_path / plan.ALPHA_COMPLETION_CLOSEOUT, _closeout())
    _write_json(tmp_path / plan.RUN_STATUS, _run_status())
    _write_text(
        tmp_path / plan.ADVERSARIAL_AUDIT,
        "No complete current-scope trial log. PBO, Deflated Sharpe, and "
        "multiple-testing remain blocked.\n",
    )
    return tmp_path / plan.DEFAULT_REPORTS_ROOT


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, **kwargs)
    return plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )


def test_schema_remediation_plan_passes_with_explicit_unresolved_markers(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == plan.PASS_STATUS
    assert report["summary"]["candidate_trial_search_ledger_row_count"] == 27
    assert report["summary"]["registry_json_source_report_ref_count"] == 21
    assert report["summary"]["present_registry_json_source_report_ref_count"] == 7
    assert report["summary"]["missing_registry_json_source_report_ref_count"] == 14
    assert report["summary"]["trial_ledger_search_path_complete"] is False
    assert report["summary"]["pbo_applicability_ready"] is False
    assert report["summary"]["statistical_validity_ready"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["unresolved_field_counts"]["search_family_id"] == 27
    assert all(
        field in row
        for row in report["candidate_trial_search_ledger_rows"]
        for field in plan.REQUIRED_FIELDS
    )
    assert any(
        item["resolution"] == plan.UNRESOLVED
        for item in report["source_report_reference_inventory"]
        if item["exists"] is False
    )


def test_missing_upstream_reconciliation_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / plan.UPSTREAM_RECONCILIATION).unlink()

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("upstream" in failure.lower() for failure in report["failures"])


def test_malformed_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / plan.EXPERIMENT_LEDGER).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_malformed_registry_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, registry={"schema_version": 1, "hypotheses": "bad"})

    assert report["status"] == plan.FAIL_STATUS
    assert any("registry" in failure.lower() for failure in report["failures"])


def test_malformed_trial_statuses_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / plan.TARGET_TRIAL_STATUSES).write_text("{bad json\n", encoding="utf-8")

    report = plan.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_unknown_trial_status_hypothesis_fails_closed(tmp_path: Path) -> None:
    rows = _trial_status_rows()
    rows[-1]["hypothesis_id"] = "unknown"

    report = _build(tmp_path, trial_status_rows=rows)

    assert report["status"] == plan.FAIL_STATUS
    assert any("identity checks" in failure.lower() for failure in report["failures"])


def test_candidate_rows_missing_required_fields_fail_closed() -> None:
    row_failures, messages = plan.validate_candidate_rows(
        rows=[{"row_id": "bad"}],
        source_report_refs=[],
    )

    assert row_failures
    assert any("missing required fields" in message for message in messages)


def test_missing_source_reports_must_be_explicitly_unresolved() -> None:
    complete_row = {field: "value" for field in plan.REQUIRED_FIELDS}
    complete_row["row_id"] = "complete"

    _row_failures, messages = plan.validate_candidate_rows(
        rows=[complete_row],
        source_report_refs=[
            {
                "hypothesis_id": "h00",
                "path": "reports/pipeline_audit/missing.json",
                "exists": False,
                "resolution": "PRESENT_LOCAL_EVIDENCE",
            }
        ],
    )

    assert any("not explicitly marked unresolved" in message for message in messages)


def test_readiness_or_statistical_upgrade_fails_closed(tmp_path: Path) -> None:
    promotion = _phase8_promotion()
    promotion["promoted"] = True
    promotion["research_alpha_ready"] = True
    statistical = copy.deepcopy(_statistical_summary())
    required = statistical["required_checks"]
    assert isinstance(required, dict)
    required["pbo"]["status"] = "PASS"  # type: ignore[index]

    report = _build(
        tmp_path,
        phase8_promotion=promotion,
        statistical_summary=statistical,
    )

    assert report["status"] == plan.FAIL_STATUS
    assert any("upgraded" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = plan.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        plan.REPORT_JSON,
        plan.REPORT_MD,
    ]
    payload = json.loads((reports_root / plan.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["trial_ledger_search_path_complete"] is False
    assert payload["summary"]["promotion_allowed"] is False
