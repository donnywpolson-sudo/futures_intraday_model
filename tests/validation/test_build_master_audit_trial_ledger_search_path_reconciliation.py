from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import (
    build_master_audit_trial_ledger_search_path_reconciliation as trial,
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


def _partial_report() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_STATISTICAL_VALIDITY_PARTIAL_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "data_integrity_ready": True,
            "trial_ledger_search_path_complete": False,
            "pbo_status": "FAIL_MISSING_TRIAL_LOG",
            "deflated_sharpe_status": "FAIL_MISSING_TRIAL_LOG",
            "multiple_testing_status": "FAIL_MISSING_TRIAL_LOG",
            "statistical_validity_ready": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _statistical_summary() -> dict[str, object]:
    return {
        "status": "FAIL",
        "statistical_validity_ready": False,
        "failure_count": 5,
        "required_checks": {
            "pbo": {"status": "FAIL_MISSING_TRIAL_LOG", "trial_count": None},
            "deflated_sharpe": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
            "multiple_testing_adjustment": {
                "status": "FAIL_MISSING_TRIAL_LOG",
                "trial_count": None,
            },
            "probabilistic_sharpe": {"status": "FAIL"},
            "bootstrap_confidence_intervals": {"status": "PASS", "sample_count": 500},
            "parameter_stability": {"status": "PASS"},
            "regime_breakdowns": {"status": "FAIL"},
        },
    }


def _alpha_gap_matrix() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "alpha_evidence_ready": False,
        "verdict": "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
        "buckets": [
            {"bucket_id": "statistical_pbo", "status": "MISSING_EVIDENCE"},
            {
                "bucket_id": "statistical_deflated_sharpe",
                "status": "MISSING_EVIDENCE",
            },
            {"bucket_id": "statistical_multiple_testing", "status": "MISSING_EVIDENCE"},
        ],
    }


def _closeout() -> dict[str, object]:
    return {
        "status": "PASS_REPORT_WRITTEN",
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "verdict": "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
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


def _experiment_rows() -> list[dict[str, object]]:
    return [
        {
            "timestamp_utc": f"2026-07-0{idx}T00:00:00Z",
            "command": "report_only",
            "profile": "current_line",
            "status": "BLOCKED",
            "evidence_path": f"reports/experiments/evidence_{idx}.json",
        }
        for idx in range(1, 5)
    ]


def _registry() -> dict[str, object]:
    hypotheses: list[dict[str, object]] = [
        {
            "target_hypothesis_id": "h00",
            "status": "FROZEN",
            "wfa_allowed": True,
        }
    ]
    hypotheses.extend(
        {
            "target_hypothesis_id": f"h{idx:02d}",
            "status": "REJECTED",
            "wfa_allowed": False,
        }
        for idx in range(1, 17)
    )
    return {"schema_version": "1.0", "hypotheses": hypotheses}


def _trial_status_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "trial_id": f"candidate-{idx:02d}",
            "hypothesis_id": f"h{idx:02d}",
            "status": "CANDIDATE",
            "evidence": [],
        }
        for idx in range(17)
    ]
    rows.extend(
        {
            "trial_id": f"terminal-{idx:02d}",
            "hypothesis_id": f"h{idx:02d}",
            "status": "REJECTED" if idx else "FROZEN",
            "evidence": [f"reports/target_hypotheses/evidence_{idx}.json"],
        }
        for idx in range(5)
    )
    return rows


def _run_status() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
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
    partial_report: dict[str, object] | None = None,
    statistical_summary: dict[str, object] | None = None,
    alpha_gap_matrix: dict[str, object] | None = None,
    closeout: dict[str, object] | None = None,
    experiment_rows: list[dict[str, object]] | None = None,
    registry: dict[str, object] | None = None,
    trial_status_rows: list[dict[str, object]] | None = None,
    run_status: dict[str, object] | None = None,
) -> Path:
    _write_json(tmp_path / trial.PARTIAL_RECONCILIATION, partial_report or _partial_report())
    _write_json(
        tmp_path / trial.STATISTICAL_SUMMARY,
        statistical_summary or _statistical_summary(),
    )
    _write_json(tmp_path / trial.ALPHA_GAP_MATRIX, alpha_gap_matrix or _alpha_gap_matrix())
    _write_json(tmp_path / trial.ALPHA_COMPLETION_CLOSEOUT, closeout or _closeout())
    _write_jsonl(tmp_path / trial.EXPERIMENT_LEDGER, experiment_rows or _experiment_rows())
    _write_json(tmp_path / trial.TARGET_REGISTRY, registry or _registry())
    _write_jsonl(
        tmp_path / trial.TARGET_TRIAL_STATUSES,
        trial_status_rows or _trial_status_rows(),
    )
    _write_json(tmp_path / trial.RUN_STATUS, run_status or _run_status())
    _write_text(
        tmp_path / trial.ADVERSARIAL_AUDIT,
        "No complete current-scope trial log exists. PBO, Deflated Sharpe, "
        "and multiple-testing remain blocked.\n",
    )
    return tmp_path / trial.DEFAULT_REPORTS_ROOT


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    reports_root = _base_repo(tmp_path, **kwargs)
    return trial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )


def test_trial_ledger_search_path_reconciliation_passes_current_blocked_state(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == trial.PASS_STATUS
    assert report["summary"]["trial_ledger_search_path_complete"] is False
    assert report["summary"]["experiment_ledger_row_count"] == 4
    assert report["summary"]["target_registry_hypothesis_count"] == 17
    assert report["summary"]["target_trial_status_row_count"] == 22
    assert report["summary"]["frozen_hypothesis_count"] == 1
    assert report["summary"]["pbo_status"] == "FAIL_MISSING_TRIAL_LOG"
    assert report["summary"]["deflated_sharpe_status"] == "FAIL_MISSING_TRIAL_LOG"
    assert report["summary"]["multiple_testing_status"] == "FAIL_MISSING_TRIAL_LOG"
    assert report["summary"]["statistical_validity_ready"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert report["summary"]["experiment_ledger_missing_field_counts"]["run_id"] == 4


def test_missing_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / trial.EXPERIMENT_LEDGER).unlink()

    report = trial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == trial.FAIL_STATUS
    assert any("experiment ledger" in failure.lower() for failure in report["failures"])


def test_malformed_experiment_ledger_fails_closed(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)
    (tmp_path / trial.EXPERIMENT_LEDGER).write_text("{bad json\n", encoding="utf-8")

    report = trial.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == trial.FAIL_STATUS
    assert any("json parse error" in failure.lower() for failure in report["failures"])


def test_malformed_registry_fails_closed(tmp_path: Path) -> None:
    registry = {"schema_version": "1.0", "hypotheses": "bad"}

    report = _build(tmp_path, registry=registry)

    assert report["status"] == trial.FAIL_STATUS
    assert any("target registry counts" in failure.lower() for failure in report["failures"])


def test_unknown_trial_status_hypothesis_fails_closed(tmp_path: Path) -> None:
    rows = _trial_status_rows()
    rows[-1]["hypothesis_id"] = "unknown"

    report = _build(tmp_path, trial_status_rows=rows)

    assert report["status"] == trial.FAIL_STATUS
    assert any("unknown hypotheses" in failure.lower() for failure in report["failures"])


def test_non_frozen_wfa_allowed_fails_closed(tmp_path: Path) -> None:
    registry = _registry()
    hypotheses = registry["hypotheses"]
    assert isinstance(hypotheses, list)
    hypotheses[1]["wfa_allowed"] = True

    report = _build(tmp_path, registry=registry)

    assert report["status"] == trial.FAIL_STATUS
    assert any("wfa policy" in failure.lower() for failure in report["failures"])


def test_terminal_trial_status_without_evidence_path_fails_closed(tmp_path: Path) -> None:
    rows = _trial_status_rows()
    rows[-1]["evidence"] = []

    report = _build(tmp_path, trial_status_rows=rows)

    assert report["status"] == trial.FAIL_STATUS
    assert any("without evidence paths" in failure.lower() for failure in report["failures"])


def test_upstream_partial_report_not_pass_fails_closed(tmp_path: Path) -> None:
    partial_report = _partial_report()
    partial_report["status"] = "FAIL"

    report = _build(tmp_path, partial_report=partial_report)

    assert report["status"] == trial.FAIL_STATUS
    assert any("upstream statistical partial" in failure.lower() for failure in report["failures"])


def test_readiness_or_promotion_upgrade_fails_closed(tmp_path: Path) -> None:
    partial_report = _partial_report()
    summary = partial_report["summary"]
    assert isinstance(summary, dict)
    summary["statistical_validity_ready"] = True
    summary["promotion_allowed"] = True

    report = _build(tmp_path, partial_report=partial_report)

    assert report["status"] == trial.FAIL_STATUS
    assert any("readiness" in failure.lower() for failure in report["failures"])


def test_statistical_required_check_upgrade_fails_closed(tmp_path: Path) -> None:
    statistical = copy.deepcopy(_statistical_summary())
    checks = statistical["required_checks"]
    assert isinstance(checks, dict)
    checks["pbo"]["status"] = "PASS"  # type: ignore[index]

    report = _build(tmp_path, statistical_summary=statistical)

    assert report["status"] == trial.FAIL_STATUS
    assert any("missing-trial-log" in failure.lower() for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = trial.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        trial.REPORT_JSON,
        trial.REPORT_MD,
    ]
    payload = json.loads((reports_root / trial.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["statistical_validity_ready"] is False
    assert payload["summary"]["model_trust_ready"] is False
    assert payload["summary"]["promotion_allowed"] is False
    assert payload["summary"]["trial_ledger_search_path_complete"] is False
