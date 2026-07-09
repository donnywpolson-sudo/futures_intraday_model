from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_alpha_evidence_gap_matrix as matrix


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _baseline_row(baseline_id: str, status: str = matrix.PASS, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {"baseline_id": baseline_id, "status": status}
    row.update(extra)
    return row


def _passing_phase8() -> dict[str, object]:
    return {
        "promotion_gate": {
            "model_promotion_allowed": True,
            "promotion_blockers": [],
            "gate_config": {"max_turnover_per_bar": 0.10},
        },
        "promotion_metric_gate": {
            "cost_execution_stress_gate": {"status": matrix.PASS},
            "capacity_liquidity_gate": {"status": matrix.PASS, "policy": "capacity evidence present"},
        },
        "costed_oos": {"turnover_per_bar": 0.01},
        "execution_realism_gate": {
            "check_results": {
                "delay_stress": {"status": matrix.PASS},
                "liquidity_window": {"status": matrix.PASS},
                "spread_slippage": {"status": matrix.PASS},
                "partial_fills_rejects": {"status": matrix.PASS},
            }
        },
        "blockers": [],
    }


def _passing_failure_analysis(*, include_carry: bool = True, beats_no_trade: bool = True) -> dict[str, object]:
    baselines = [
        _baseline_row("candidate"),
        _baseline_row("no_trade"),
        _baseline_row("cost_only"),
        _baseline_row("random_entry", candidate_beats_random_median=True),
        _baseline_row("simple_trend"),
        _baseline_row("simple_mean_reversion"),
    ]
    if include_carry:
        baselines.append(_baseline_row("simple_carry"))
    return {
        "baseline_comparison_gate": {
            "status": matrix.PASS if beats_no_trade and include_carry else matrix.FAIL,
            "candidate_beats_no_trade": beats_no_trade,
            "baselines": baselines,
        },
        "capacity_liquidity_gate": {"status": matrix.PASS, "policy": "capacity evidence present"},
    }


def _passing_statistical_validity() -> dict[str, object]:
    return {
        "required_checks": {
            "label_shuffle": {"status": matrix.PASS},
            "timing_shift": {"status": matrix.PASS},
            "pbo": {"status": matrix.PASS},
            "deflated_sharpe": {"status": matrix.PASS},
            "probabilistic_sharpe": {"status": matrix.PASS},
            "bootstrap_confidence_intervals": {"status": matrix.PASS},
            "multiple_testing_adjustment": {"status": matrix.PASS},
            "parameter_stability": {"status": matrix.PASS},
            "regime_breakdowns": {"status": matrix.PASS},
        }
    }


def _write_fixture(
    tmp_path: Path,
    *,
    phase8: dict[str, object] | None = None,
    failure: dict[str, object] | None = None,
    statistical: dict[str, object] | None = None,
) -> dict[str, Path]:
    paths = {
        "phase8": _write_json(tmp_path / "reports" / "phase8.json", phase8 or _passing_phase8()),
        "failure": _write_json(
            tmp_path / "reports" / "failure.json",
            failure or _passing_failure_analysis(),
        ),
        "statistical": _write_json(
            tmp_path / "reports" / "statistical.json",
            statistical or _passing_statistical_validity(),
        ),
        "registry": _write_json(
            tmp_path / "manifests" / "target_hypotheses" / "registry.json",
            {"hypotheses": []},
        ),
    }
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "costs.yaml").write_text("costs: {}\n", encoding="utf-8")
    (tmp_path / "configs" / "models.yaml").write_text("models: {}\n", encoding="utf-8")
    (tmp_path / "configs" / "alpha_tiered.yaml").write_text("profiles: {}\n", encoding="utf-8")
    ledger = tmp_path / "reports" / "experiments" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('{"trial": 1}\n', encoding="utf-8")
    paths["ledger"] = ledger
    return paths


def _build(tmp_path: Path, paths: dict[str, Path]) -> dict[str, object]:
    return matrix.build_alpha_evidence_gap_matrix(
        repo_root=tmp_path,
        run_id="fixture",
        phase8_decision_path=paths["phase8"],
        failure_analysis_path=paths["failure"],
        statistical_validity_path=paths["statistical"],
        experiment_ledger_path=paths["ledger"],
        hypothesis_registry_path=paths["registry"],
        costs_config_path=tmp_path / "configs" / "costs.yaml",
        models_config_path=tmp_path / "configs" / "models.yaml",
        profile_config_path=tmp_path / "configs" / "alpha_tiered.yaml",
        generated_at_utc="2026-07-09T00:00:00+00:00",
        write_reports=False,
    )


def _bucket(result: dict[str, object], bucket_id: str) -> dict[str, object]:
    buckets = result["buckets"]
    assert isinstance(buckets, list)
    return next(row for row in buckets if isinstance(row, dict) and row["bucket_id"] == bucket_id)


def test_all_required_evidence_present_returns_ready(tmp_path: Path) -> None:
    result = _build(tmp_path, _write_fixture(tmp_path))

    assert result["alpha_evidence_ready"] is True
    assert result["verdict"] == matrix.READY_VERDICT
    assert set(result["bucket_status_counts"]) == {matrix.PASS}


def test_missing_simple_carry_returns_not_ready(tmp_path: Path) -> None:
    paths = _write_fixture(
        tmp_path,
        failure=_passing_failure_analysis(include_carry=False),
    )

    result = _build(tmp_path, paths)

    assert result["alpha_evidence_ready"] is False
    assert result["verdict"] == matrix.PAUSE_VERDICT
    assert _bucket(result, "baseline_simple_carry_term_structure")["status"] == matrix.MISSING


def test_failed_no_trade_comparison_returns_not_ready(tmp_path: Path) -> None:
    paths = _write_fixture(
        tmp_path,
        failure=_passing_failure_analysis(beats_no_trade=False),
    )

    result = _build(tmp_path, paths)

    assert result["alpha_evidence_ready"] is False
    assert _bucket(result, "baseline_no_trade")["status"] == matrix.FAIL


def test_missing_trial_log_dependent_statistics_return_not_ready(tmp_path: Path) -> None:
    statistical = _passing_statistical_validity()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["pbo"] = {"status": "FAIL_MISSING_TRIAL_LOG"}  # type: ignore[index]
    checks["deflated_sharpe"] = {"status": "FAIL_MISSING_TRIAL_LOG"}  # type: ignore[index]
    checks["multiple_testing_adjustment"] = {"status": "FAIL_MISSING_TRIAL_LOG"}  # type: ignore[index]
    paths = _write_fixture(tmp_path, statistical=statistical)

    result = _build(tmp_path, paths)

    assert result["alpha_evidence_ready"] is False
    assert _bucket(result, "statistical_pbo")["status"] == matrix.MISSING
    assert _bucket(result, "statistical_deflated_sharpe")["status"] == matrix.MISSING
    assert _bucket(result, "statistical_multiple_testing")["status"] == matrix.MISSING


def test_missing_execution_capacity_and_fill_evidence_return_not_ready(tmp_path: Path) -> None:
    phase8 = _passing_phase8()
    phase8.pop("execution_realism_gate")
    failure = _passing_failure_analysis()
    failure["capacity_liquidity_gate"] = {"status": matrix.MISSING, "policy": "capacity missing"}
    paths = _write_fixture(tmp_path, phase8=phase8, failure=failure)

    result = _build(tmp_path, paths)

    assert result["alpha_evidence_ready"] is False
    assert _bucket(result, "execution_capacity")["status"] == matrix.MISSING
    assert _bucket(result, "execution_partial_fills_rejects")["status"] == matrix.MISSING


def test_tier1_style_failed_metrics_keep_modeling_paused(tmp_path: Path) -> None:
    phase8 = _passing_phase8()
    phase8["promotion_gate"] = {
        "model_promotion_allowed": False,
        "promotion_blockers": [
            "nonpositive net_return_dollars for markets: ['ES']",
            "nonpositive net_return_dollars for folds: ['ES_research_0001']",
        ],
        "gate_config": {"max_turnover_per_bar": 0.10},
    }
    phase8["promotion_metric_gate"] = {
        "cost_execution_stress_gate": {"status": matrix.FAIL},
        "capacity_liquidity_gate": {"status": matrix.MISSING},
    }
    failure = _passing_failure_analysis(beats_no_trade=False)
    statistical = _passing_statistical_validity()
    checks = statistical["required_checks"]  # type: ignore[index]
    checks["probabilistic_sharpe"] = {"status": matrix.FAIL}  # type: ignore[index]
    paths = _write_fixture(tmp_path, phase8=phase8, failure=failure, statistical=statistical)

    result = _build(tmp_path, paths)

    assert result["alpha_evidence_ready"] is False
    assert result["verdict"] == matrix.PAUSE_VERDICT
    assert _bucket(result, "execution_cost_stress")["status"] == matrix.FAIL
    assert _bucket(result, "stability_fold_market_year_session")["status"] == matrix.FAIL


def test_cli_writes_report_and_returns_zero_by_default(tmp_path: Path, capsys) -> None:
    paths = _write_fixture(
        tmp_path,
        failure=_passing_failure_analysis(beats_no_trade=False),
    )
    report_root = tmp_path / "reports" / "model_trust_audit" / "alpha_matrix"

    exit_code = matrix.main(
        [
            "--repo-root",
            str(tmp_path),
            "--run-id",
            "fixture",
            "--phase8-decision",
            str(paths["phase8"]),
            "--failure-analysis",
            str(paths["failure"]),
            "--statistical-validity",
            str(paths["statistical"]),
            "--experiment-ledger",
            str(paths["ledger"]),
            "--hypothesis-registry",
            str(paths["registry"]),
            "--costs-config",
            str(tmp_path / "configs" / "costs.yaml"),
            "--models-config",
            str(tmp_path / "configs" / "models.yaml"),
            "--profile-config",
            str(tmp_path / "configs" / "alpha_tiered.yaml"),
            "--report-root",
            str(report_root),
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert matrix.PAUSE_VERDICT in stdout
    assert (report_root / "alpha_evidence_gap_matrix.json").is_file()
    written = json.loads((report_root / "alpha_evidence_gap_matrix.json").read_text(encoding="utf-8"))
    assert written["alpha_evidence_ready"] is False
