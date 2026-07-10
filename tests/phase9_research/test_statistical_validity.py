from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.statistical_validity import build_statistical_validity_report  # noqa: E402
from tests.phase8_model_selection.test_evaluate_predictions import (  # noqa: E402
    _policy,
    _write_costs,
    _write_manifest,
    _write_models,
    _write_predictions,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _trial_search_ledger(path: Path, **summary_overrides: object) -> Path:
    summary = {
        "trial_ledger_search_path_complete": True,
        "family_metadata_row_count": 22,
        "search_family_count": 10,
        "multiple_testing_family_count": 2,
        "statistical_recompute_executed": False,
        "statistical_validity_ready": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
    }
    summary.update(summary_overrides)
    return _write_json(
        path,
        {
            "status": "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY",
            "summary": summary,
        },
    )


def test_statistical_validity_fails_closed_without_trial_log(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert result["statistical_validity_ready"] is False
    assert result["required_checks"]["pbo"]["status"] == "FAIL_MISSING_TRIAL_LOG"
    assert result["required_checks"]["multiple_testing_adjustment"]["status"] == "FAIL_MISSING_TRIAL_LOG"
    bootstrap = pd.read_csv(
        tmp_path
        / "reports"
        / "statistical_validity"
        / "baseline"
        / "bootstrap_confidence_intervals.csv"
    )
    assert set(bootstrap["metric"]) >= {
        "net_return_dollars",
        "sharpe_like",
        "average_net_edge_per_trade",
    }


def test_statistical_validity_uses_trial_search_ledger_for_bounded_recompute(
    tmp_path: Path,
) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    trial_search_path = _trial_search_ledger(
        tmp_path / "reports" / "master_audit" / "post_mutation.json"
    )

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        trial_search_ledger_path=trial_search_path,
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert result["statistical_validity_ready"] is False
    assert result["trial_search_evidence"]["trial_count"] == 22
    assert result["trial_search_evidence"]["search_family_count"] == 10
    assert result["trial_search_evidence"]["multiple_testing_family_count"] == 2
    assert result["required_checks"]["pbo"]["status"] == "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
    assert result["required_checks"]["pbo"]["trial_count"] == 22
    assert (
        result["required_checks"]["deflated_sharpe"]["status"]
        == "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
    )
    assert result["required_checks"]["deflated_sharpe"]["trial_count"] == 22
    assert (
        result["required_checks"]["multiple_testing_adjustment"]["status"]
        == "FAIL_BONFERRONI_ADJUSTED_PSR"
    )
    assert result["required_checks"]["multiple_testing_adjustment"]["trial_count"] == 22
    assert result["model_promotion_allowed"] is False


def test_trial_search_ledger_count_drift_fails_closed(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    trial_search_path = _trial_search_ledger(
        tmp_path / "reports" / "master_audit" / "post_mutation.json",
        family_metadata_row_count=21,
    )

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        trial_search_ledger_path=trial_search_path,
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert any("family_metadata_row_count" in failure for failure in result["failures"])
    assert "trial_search_evidence" not in result


def test_trial_search_ledger_model_or_promotion_flag_fails_closed(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    trial_search_path = _trial_search_ledger(
        tmp_path / "reports" / "master_audit" / "post_mutation.json",
        promotion_allowed=True,
    )

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        trial_search_ledger_path=trial_search_path,
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert any("promotion_allowed" in failure for failure in result["failures"])
    assert "trial_search_evidence" not in result


def test_legacy_trial_log_behavior_is_preserved(tmp_path: Path) -> None:
    prediction_path = _write_predictions(
        tmp_path / "data" / "predictions" / "baseline" / "oos_predictions.parquet"
    )
    manifest_path = _write_manifest(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        prediction_path,
    )
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    models_path = _write_models(tmp_path / "configs" / "models.yaml")
    trial_log = _write_json(tmp_path / "reports" / "experiments" / "trial_log.json", {"trial_count": 3})

    result = build_statistical_validity_report(
        predictions_path=prediction_path,
        predictions_manifest=manifest_path,
        costs_config=costs_path,
        models_config=models_path,
        output_root=tmp_path / "reports" / "statistical_validity" / "baseline",
        run="baseline",
        policy=_policy(),
        trial_log_path=trial_log,
        bootstrap_samples=50,
        bootstrap_seed=123,
    )

    assert result["status"] == "FAIL"
    assert result["required_checks"]["pbo"]["status"] == "FAIL_REQUIRES_VARIANT_MATRIX"
    assert result["required_checks"]["pbo"]["trial_count"] == 3
    assert result["required_checks"]["deflated_sharpe"]["status"] == "FAIL"
    assert result["required_checks"]["multiple_testing_adjustment"]["status"] == "FAIL"
    assert "trial_search_evidence" not in result
