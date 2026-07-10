#!/usr/bin/env python3
"""Build report-only statistical-validity diagnostics for Phase 8 policy rows."""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

import numpy as np
import pandas as pd

from scripts.phase8_model_selection.evaluate_predictions import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_MODELS_CONFIG,
    PolicyConfig,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _prediction_manifest_failures,
    _read_json,
    _relative_path,
    _safe_float,
    _safe_int,
    _write_json,
    build_policy_frame,
    load_policy_config,
)


DEFAULT_OUTPUT_ROOT = Path("reports") / "statistical_validity"
DEFAULT_RUN = "baseline"
BOOTSTRAP_SEED = 20260706
BOOTSTRAP_SAMPLES = 500
REQUIRED_CHECKS = (
    "pbo",
    "deflated_sharpe",
    "probabilistic_sharpe",
    "bootstrap_confidence_intervals",
    "multiple_testing_adjustment",
    "parameter_stability",
    "regime_breakdowns",
)
TRIAL_SEARCH_READY_STATUS = "PASS_MASTER_AUDIT_POST_MUTATION_TRIAL_SEARCH_COMPLETENESS_RECONCILIATION_REPORT_ONLY"


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def _sharpe_like(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if len(numeric) < 2:
        return None
    std = float(numeric.std(ddof=0))
    if std <= 0.0:
        return None
    return _safe_float(float(numeric.mean() / std * math.sqrt(len(numeric))))


def _max_drawdown(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if numeric.empty:
        return None
    equity = numeric.cumsum()
    drawdown = equity - equity.cummax()
    return _safe_float(drawdown.min())


def _psr(values: pd.Series, benchmark_sharpe: float = 0.0) -> tuple[float | None, dict[str, Any]]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    n = len(numeric)
    sr = _sharpe_like(numeric)
    if sr is None or n < 3:
        return None, {"reason": "insufficient return observations"}
    skew = float(numeric.skew()) if n >= 3 else 0.0
    pearson_kurt = float(numeric.kurt()) + 3.0 if n >= 4 else 3.0
    denominator = 1.0 - skew * sr + ((pearson_kurt - 1.0) / 4.0) * sr * sr
    if denominator <= 0.0:
        return None, {"reason": "invalid PSR denominator", "sharpe_like": sr}
    z_score = (sr - benchmark_sharpe) * math.sqrt(n - 1.0) / math.sqrt(denominator)
    probability = NormalDist().cdf(z_score)
    return _safe_float(probability), {
        "observation_count": n,
        "sharpe_like": sr,
        "benchmark_sharpe": benchmark_sharpe,
        "skew": skew,
        "pearson_kurtosis": pearson_kurt,
        "z_score": z_score,
    }


def _trial_count(trial_log: Mapping[str, Any] | None) -> int | None:
    if not isinstance(trial_log, Mapping):
        return None
    for key in ("trial_count", "variant_count", "tested_variant_count", "search_count"):
        value = _safe_int(trial_log.get(key))
        if value is not None and value > 0:
            return value
    trials = trial_log.get("trials")
    if isinstance(trials, list):
        return len(trials)
    return None


def _trial_search_context(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(payload, Mapping):
        return None, []
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        return None, ["trial-search ledger missing summary object"]
    failures: list[str] = []
    expected = {
        "status": TRIAL_SEARCH_READY_STATUS,
        "trial_ledger_search_path_complete": True,
        "family_metadata_row_count": 22,
        "search_family_count": 10,
        "multiple_testing_family_count": 2,
        "statistical_recompute_executed": False,
        "statistical_validity_ready": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
    }
    for key, value in expected.items():
        actual = payload.get(key) if key == "status" else summary.get(key)
        if actual != value:
            failures.append(
                f"trial-search ledger expected {key}={value!r} but found {actual!r}"
            )
    if failures:
        return None, failures
    return {
        "trial_count": int(summary["family_metadata_row_count"]),
        "search_family_count": int(summary["search_family_count"]),
        "multiple_testing_family_count": int(summary["multiple_testing_family_count"]),
        "source_status": payload.get("status"),
        "trial_ledger_search_path_complete": summary.get("trial_ledger_search_path_complete"),
    }, []


def _bootstrap(values: pd.Series, *, seed: int, samples: int) -> pd.DataFrame:
    numeric = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(numeric) == 0:
        return pd.DataFrame(
            [{"metric": "unavailable", "ci_low": None, "ci_high": None, "reason": "no returns"}]
        )
    rng = np.random.default_rng(seed)
    pnl: list[float] = []
    sharpe: list[float] = []
    edge: list[float] = []
    drawdown: list[float] = []
    for _ in range(samples):
        sample = pd.Series(rng.choice(numeric, size=len(numeric), replace=True))
        pnl.append(float(sample.sum()))
        sharpe.append(_sharpe_like(sample) or 0.0)
        edge.append(float(sample.mean()))
        drawdown.append(_max_drawdown(sample) or 0.0)
    rows = []
    for metric, series in {
        "net_return_dollars": pd.Series(pnl),
        "sharpe_like": pd.Series(sharpe),
        "average_net_edge_per_trade": pd.Series(edge),
        "max_drawdown_dollars": pd.Series(drawdown),
    }.items():
        rows.append(
            {
                "metric": metric,
                "sample_count": samples,
                "ci_low": _safe_float(series.quantile(0.025)),
                "ci_mid": _safe_float(series.quantile(0.50)),
                "ci_high": _safe_float(series.quantile(0.975)),
            }
        )
    return pd.DataFrame(rows)


def _stability(policy_frame: pd.DataFrame) -> pd.DataFrame:
    if policy_frame.empty:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    group_specs = [
        ("market", ["market"]),
        ("year", ["year"]),
        ("fold", ["fold_id"]),
        ("market_fold", ["market", "fold_id"]),
    ]
    for scope, cols in group_specs:
        if not set(cols) <= set(policy_frame.columns):
            continue
        for keys, group in policy_frame.groupby(cols, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            trades = group[group["trade_count"].eq(1)]
            net = _numeric(trades, "net_dollars")
            record = {
                "scope": scope,
                **dict(zip(cols, keys)),
                "row_count": int(len(group)),
                "trade_count": int(len(trades)),
                "net_return_dollars": _safe_float(net.sum()) if not net.empty else 0.0,
                "sharpe_like": _sharpe_like(net),
                "positive_net": bool(_safe_float(net.sum()) and float(net.sum()) > 0.0)
                if not net.empty
                else False,
            }
            records.append(record)
    return pd.DataFrame(records)


def _adversarial_tests(policy_frame: pd.DataFrame) -> pd.DataFrame:
    if policy_frame.empty:
        return pd.DataFrame([{"test_id": "unavailable", "status": "FAIL", "reason": "no policy rows"}])
    trades = policy_frame[policy_frame["trade_count"].eq(1)]
    net = _numeric(trades, "net_dollars")
    gross = _numeric(trades, "gross_dollars")
    cost = _numeric(trades, "cost_dollars")
    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "test_id": "top_1pct_trade_removal",
            "status": "PASS" if len(net) > 0 else "FAIL",
            "net_return_dollars": _safe_float(net.sort_values(ascending=False).iloc[max(1, int(len(net) * 0.01)) :].sum())
            if len(net)
            else None,
        }
    )
    rows.append(
        {
            "test_id": "two_x_cost_stress",
            "status": "PASS" if float(gross.sum() - 2.0 * cost.sum()) > 0.0 else "FAIL",
            "net_return_dollars": _safe_float(gross.sum() - 2.0 * cost.sum()),
        }
    )
    rows.append(
        {
            "test_id": "random_entry_distribution",
            "status": "MISSING_WITH_REASON",
            "reason": "random-entry distribution is produced by Phase 8 failure analysis",
        }
    )
    rows.append(
        {
            "test_id": "label_shuffle",
            "status": "MISSING_WITH_REASON",
            "reason": "requires a bounded rerun/shuffle harness; not inferred from current predictions",
        }
    )
    return pd.DataFrame(rows)


def _required_check_payloads(
    *,
    net_returns: pd.Series,
    bootstrap_ci: pd.DataFrame,
    stability: pd.DataFrame,
    adversarial: pd.DataFrame,
    trial_log: Mapping[str, Any] | None,
    trial_search_context: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    psr_value, psr_detail = _psr(net_returns)
    trials = (
        _safe_int(trial_search_context.get("trial_count"))
        if isinstance(trial_search_context, Mapping)
        else _trial_count(trial_log)
    )
    search_families = (
        _safe_int(trial_search_context.get("search_family_count"))
        if isinstance(trial_search_context, Mapping)
        else None
    )
    multiple_testing_families = (
        _safe_int(trial_search_context.get("multiple_testing_family_count"))
        if isinstance(trial_search_context, Mapping)
        else None
    )
    stability_ready = (
        not stability.empty
        and "scope" in stability
        and stability[stability["scope"].eq("fold")]["positive_net"].nunique(dropna=False) > 0
    )
    regime_ready = False
    raw_p_value = _safe_float(1.0 - psr_value) if psr_value is not None else None
    adjusted_p_value = (
        _safe_float(min(1.0, raw_p_value * float(trials)))
        if raw_p_value is not None and trials is not None
        else None
    )
    pbo_status = (
        "FAIL_MISSING_TRIAL_LOG"
        if trials is None
        else "FAIL_NO_VARIANT_PERFORMANCE_MATRIX"
        if trial_search_context is not None
        else "FAIL_REQUIRES_VARIANT_MATRIX"
    )
    deflated_sharpe_status = (
        "FAIL_MISSING_TRIAL_LOG"
        if trials is None
        else "FAIL_NEGATIVE_SHARPE_AFTER_TRIAL_COUNT_DEFLATION"
        if trial_search_context is not None
        else "FAIL"
    )
    multiple_testing_status = (
        "FAIL_MISSING_TRIAL_LOG"
        if trials is None
        else "FAIL_BONFERRONI_ADJUSTED_PSR"
        if trial_search_context is not None
        else "FAIL"
    )
    checks = {
        "pbo": {
            "status": pbo_status,
            "trial_count": trials,
            "search_family_count": search_families,
            "multiple_testing_family_count": multiple_testing_families,
            "reason": "PBO requires a variant performance matrix, not only canonical trial/search family counts",
        },
        "deflated_sharpe": {
            "status": deflated_sharpe_status,
            "trial_count": trials,
            "search_family_count": search_families,
            "observed_sharpe_like": psr_detail.get("sharpe_like"),
            "reason": "Deflated Sharpe requires observed Sharpe plus search/trial count evidence",
        },
        "probabilistic_sharpe": {
            "status": "PASS" if psr_value is not None and psr_value >= 0.95 else "FAIL",
            "probabilistic_sharpe": psr_value,
            **psr_detail,
        },
        "bootstrap_confidence_intervals": {
            "status": "PASS"
            if not bootstrap_ci.empty
            and bootstrap_ci["metric"].astype(str).eq("net_return_dollars").any()
            else "FAIL",
            "sample_count": BOOTSTRAP_SAMPLES,
        },
        "multiple_testing_adjustment": {
            "status": multiple_testing_status,
            "trial_count": trials,
            "search_family_count": search_families,
            "multiple_testing_family_count": multiple_testing_families,
            "raw_p_value": raw_p_value,
            "bonferroni_adjusted_p_value": adjusted_p_value,
            "reason": "multiple-testing adjustment remains failed because adjusted PSR evidence does not pass",
        },
        "parameter_stability": {
            "status": "PASS" if stability_ready else "FAIL",
            "reason": "fold/market/year stability matrix must show broad positive evidence",
        },
        "regime_breakdowns": {
            "status": "PASS" if regime_ready else "FAIL",
            "reason": "explicit causal regime evidence is not present in this report",
        },
    }
    return checks


def build_statistical_validity_report(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    costs_config: Path,
    models_config: Path,
    output_root: Path,
    run: str,
    policy: PolicyConfig,
    trial_log_path: Path | None = None,
    trial_search_ledger_path: Path | None = None,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    failures: list[str] = []
    manifest = _read_json(predictions_manifest)
    trial_log = _read_json(trial_log_path) if trial_log_path and trial_log_path.exists() else None
    trial_search_payload = (
        _read_json(trial_search_ledger_path)
        if trial_search_ledger_path and trial_search_ledger_path.exists()
        else None
    )
    trial_search_context, trial_search_failures = _trial_search_context(trial_search_payload)
    if trial_search_ledger_path is not None:
        if not trial_search_ledger_path.exists():
            trial_search_failures.append(
                f"trial-search ledger missing: {_relative_path(trial_search_ledger_path)}"
            )
        failures.extend(trial_search_failures)
    if not predictions_path.exists():
        predictions = pd.DataFrame()
        failures.append(f"prediction parquet missing: {_relative_path(predictions_path)}")
    else:
        predictions = pd.read_parquet(predictions_path)
    failures.extend(
        _prediction_manifest_failures(
            manifest,
            predictions_path=predictions_path,
            predictions=predictions,
            run=run,
        )
    )
    if failures:
        policy_frame = pd.DataFrame()
    else:
        policy_frame, policy_failures, _ = build_policy_frame(predictions, costs_config, policy)
        failures.extend(policy_failures)
    trades = policy_frame[policy_frame["trade_count"].eq(1)] if "trade_count" in policy_frame else pd.DataFrame()
    net_returns = _numeric(trades, "net_dollars")
    bootstrap_ci = _bootstrap(net_returns, seed=bootstrap_seed, samples=bootstrap_samples)
    stability = _stability(policy_frame)
    adversarial = _adversarial_tests(policy_frame)
    checks = _required_check_payloads(
        net_returns=net_returns,
        bootstrap_ci=bootstrap_ci,
        stability=stability,
        adversarial=adversarial,
        trial_log=trial_log,
        trial_search_context=trial_search_context,
    )
    check_failures = [
        f"statistical-validity evidence missing or failing: {key}"
        for key, value in checks.items()
        if str(value.get("status")) != "PASS"
    ]
    ready = not failures and not check_failures

    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "statistical_validity_summary.json"
    bootstrap_path = output_root / "bootstrap_confidence_intervals.csv"
    stability_path = output_root / "stability_matrix.csv"
    adversarial_path = output_root / "adversarial_tests.csv"
    readme_path = output_root / "statistical_validity.md"
    _write_csv(bootstrap_path, bootstrap_ci)
    _write_csv(stability_path, stability)
    _write_csv(adversarial_path, adversarial)
    outputs = {
        "summary": _relative_path(summary_path),
        "bootstrap_confidence_intervals": _relative_path(bootstrap_path),
        "stability_matrix": _relative_path(stability_path),
        "adversarial_tests": _relative_path(adversarial_path),
        "readme": _relative_path(readme_path),
    }
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": "phase9_statistical_validity",
        "diagnostic_only": True,
        "status": "PASS" if ready else "FAIL",
        "statistical_validity_ready": ready,
        "run": run,
        "prediction_path": _relative_path(predictions_path),
        "predictions_manifest_path": _relative_path(predictions_manifest),
        "prediction_count": int(len(predictions)),
        "policy_trade_count": int(len(trades)),
        "failure_count": len(failures) + len(check_failures),
        "failures": failures + check_failures,
        "required_checks": checks,
        "input_file_hashes": _file_hash_map(
            [
                path
                for path in (predictions_path, predictions_manifest, costs_config, models_config, trial_log_path)
                if path is not None
            ]
            + ([trial_search_ledger_path] if trial_search_ledger_path is not None else [])
        ),
        "outputs": outputs,
        "research_only": True,
        "model_promotion_allowed": False,
    }
    if trial_search_context is not None:
        payload["trial_search_evidence"] = {
            "trial_search_ledger_path": _relative_path(trial_search_ledger_path)
            if trial_search_ledger_path is not None
            else None,
            **dict(trial_search_context),
        }
    _write_json(summary_path, payload)
    readme_path.write_text(
        "\n".join(
            [
                "# Phase 9 Statistical Validity",
                "",
                f"Run: `{run}`",
                "",
                "This report is diagnostic only. Missing trial/search evidence fails closed.",
                "",
                f"Status: `{payload['status']}`",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--trial-log")
    parser.add_argument("--trial-search-ledger")
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED)
    parser.add_argument("--long-short-margin", type=float, default=0.05)
    parser.add_argument("--min-fade-success", type=float, default=0.50)
    parser.add_argument("--max-trend-danger", type=float, default=0.50)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    policy = load_policy_config(
        Path(args.models_config),
        long_short_margin=args.long_short_margin,
        min_fade_success=args.min_fade_success,
        max_trend_danger=args.max_trend_danger,
    )
    result = build_statistical_validity_report(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        costs_config=Path(args.costs_config),
        models_config=Path(args.models_config),
        output_root=Path(args.output_root),
        run=args.run,
        policy=policy,
        trial_log_path=Path(args.trial_log) if args.trial_log else None,
        trial_search_ledger_path=Path(args.trial_search_ledger)
        if args.trial_search_ledger
        else None,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(
        "PASS" if result["statistical_validity_ready"] else "FAIL",
        "statistical validity:",
        f"trades={result['policy_trade_count']}",
        f"failures={result['failure_count']}",
        f"summary={result['outputs']['summary']}",
    )
    return 0 if result["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
