#!/usr/bin/env python3
"""Build a report-only baseline/null/execution evidence gap matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PASS = "PASS"
FAIL = "FAIL"
MISSING = "MISSING_EVIDENCE"
NA = "NOT_APPLICABLE_WITH_REASON"

READY_VERDICT = "BASELINE_NULL_EXECUTION_EVIDENCE_READY_FOR_PREDECLARED_MODEL_RESEARCH"
PAUSE_VERDICT = "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"

DEFAULT_RUN = "tier1_core_phase6_full_predictions_20260706"
DEFAULT_PHASE8_DECISION = (
    Path("reports") / "phase8" / DEFAULT_RUN / "alpha_promotion_decision.json"
)
DEFAULT_FAILURE_ANALYSIS = (
    Path("reports") / "failure_analysis" / DEFAULT_RUN / "failure_analysis_summary.json"
)
DEFAULT_STATISTICAL_VALIDITY = (
    Path("reports")
    / "statistical_validity"
    / DEFAULT_RUN
    / "statistical_validity_summary.json"
)
DEFAULT_EXPERIMENT_LEDGER = Path("reports") / "experiments" / "ledger.jsonl"
DEFAULT_HYPOTHESIS_REGISTRY = Path("manifests") / "target_hypotheses" / "registry.json"
DEFAULT_COSTS_CONFIG = Path("configs") / "costs.yaml"
DEFAULT_MODELS_CONFIG = Path("configs") / "models.yaml"
DEFAULT_PROFILE_CONFIG = Path("configs") / "alpha_tiered.yaml"

REQUIRED_BUCKETS = (
    "baseline_no_trade",
    "baseline_cost_only",
    "baseline_random_entry_null",
    "baseline_simple_trend",
    "baseline_simple_mean_reversion",
    "baseline_simple_carry_term_structure",
    "null_label_shuffle",
    "null_timing_shift",
    "statistical_pbo",
    "statistical_deflated_sharpe",
    "statistical_probabilistic_sharpe",
    "statistical_bootstrap_ci",
    "statistical_multiple_testing",
    "stability_parameter",
    "stability_regime_breakdowns",
    "stability_fold_market_year_session",
    "execution_cost_stress",
    "execution_delay_stress",
    "execution_turnover",
    "execution_liquidity_window",
    "execution_capacity",
    "execution_spread_slippage",
    "execution_partial_fills_rejects",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(value: str) -> str:
    cleaned = value.replace("+00:00", "Z").replace("-", "").replace(":", "")
    return cleaned.replace(".", "_")


def _resolve(repo_root: Path, path: Path | str | None) -> Path | None:
    if path is None:
        return None
    resolved = Path(path)
    return resolved if resolved.is_absolute() else repo_root / resolved


def _relative(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _read_json(path: Path | None) -> tuple[dict[str, Any], str | None]:
    if path is None:
        return {}, "path not supplied"
    if not path.exists():
        return {}, "file missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"read error: {exc}"
    if not isinstance(payload, dict):
        return {}, "JSON root is not an object"
    return payload, None


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _status_from_raw(raw: object) -> str:
    text = str(raw or "").upper()
    if text == PASS:
        return PASS
    if not text or "MISSING" in text or "UNAVAILABLE" in text:
        return MISSING
    if text in {NA, "NOT_APPLICABLE"}:
        return NA
    return FAIL


def _bucket(
    *,
    bucket_id: str,
    category: str,
    name: str,
    status: str,
    reason: str,
    evidence_paths: Sequence[str | None] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "bucket_id": bucket_id,
        "category": category,
        "name": name,
        "status": status,
        "pass": status == PASS,
        "reason": reason,
        "evidence_paths": [path for path in evidence_paths if path],
        "details": dict(details or {}),
    }


def _nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: object = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, Mapping) else {}


def _baselines_by_id(
    failure_analysis: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for gate in (
        failure_analysis.get("baseline_comparison_gate", {}),
        _nested_mapping(phase8_decision, "promotion_metric_gate", "baseline_comparison_gate"),
    ):
        if not isinstance(gate, Mapping):
            continue
        baselines = gate.get("baselines", [])
        if isinstance(baselines, list):
            rows.extend(item for item in baselines if isinstance(item, Mapping))
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        baseline_id = str(row.get("baseline_id", ""))
        if baseline_id and baseline_id not in out:
            out[baseline_id] = row
    return out


def _baseline_gate(
    failure_analysis: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
) -> Mapping[str, Any]:
    gate = failure_analysis.get("baseline_comparison_gate")
    if isinstance(gate, Mapping) and gate:
        return gate
    return _nested_mapping(phase8_decision, "promotion_metric_gate", "baseline_comparison_gate")


def _classify_baseline_row(
    *,
    bucket_id: str,
    name: str,
    baseline_id: str,
    rows: Mapping[str, Mapping[str, Any]],
    evidence_path: str | None,
    category: str = "baseline",
) -> dict[str, Any]:
    row = rows.get(baseline_id)
    if not row:
        return _bucket(
            bucket_id=bucket_id,
            category=category,
            name=name,
            status=MISSING,
            reason=f"{baseline_id} baseline evidence is missing",
            evidence_paths=[evidence_path],
        )
    status = _status_from_raw(row.get("status"))
    reason = f"{baseline_id} baseline status is {row.get('status')}"
    if status == MISSING:
        reason = str(row.get("reason") or reason)
    return _bucket(
        bucket_id=bucket_id,
        category=category,
        name=name,
        status=status,
        reason=reason,
        evidence_paths=[evidence_path],
        details={"baseline": dict(row)},
    )


def _classify_baselines(
    *,
    failure_analysis: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
    failure_path: str | None,
    phase8_path: str | None,
) -> list[dict[str, Any]]:
    rows = _baselines_by_id(failure_analysis, phase8_decision)
    gate = _baseline_gate(failure_analysis, phase8_decision)
    evidence = failure_path or phase8_path
    buckets: list[dict[str, Any]] = []

    no_trade = rows.get("no_trade")
    candidate_beats = gate.get("candidate_beats_no_trade")
    if not no_trade:
        buckets.append(
            _bucket(
                bucket_id="baseline_no_trade",
                category="baseline",
                name="No-trade baseline",
                status=MISSING,
                reason="no-trade baseline row is missing",
                evidence_paths=[evidence],
            )
        )
    elif _status_from_raw(no_trade.get("status")) != PASS:
        buckets.append(
            _bucket(
                bucket_id="baseline_no_trade",
                category="baseline",
                name="No-trade baseline",
                status=_status_from_raw(no_trade.get("status")),
                reason=f"no-trade baseline status is {no_trade.get('status')}",
                evidence_paths=[evidence],
                details={"baseline": dict(no_trade)},
            )
        )
    elif candidate_beats is False:
        buckets.append(
            _bucket(
                bucket_id="baseline_no_trade",
                category="baseline",
                name="No-trade baseline",
                status=FAIL,
                reason="candidate does not beat the no-trade baseline",
                evidence_paths=[evidence],
                details={"candidate_beats_no_trade": candidate_beats},
            )
        )
    else:
        buckets.append(
            _bucket(
                bucket_id="baseline_no_trade",
                category="baseline",
                name="No-trade baseline",
                status=PASS,
                reason="no-trade baseline is present and candidate comparison passed",
                evidence_paths=[evidence],
                details={"candidate_beats_no_trade": candidate_beats},
            )
        )

    buckets.append(
        _classify_baseline_row(
            bucket_id="baseline_cost_only",
            name="Cost-only baseline",
            baseline_id="cost_only",
            rows=rows,
            evidence_path=evidence,
        )
    )

    random_bucket = _classify_baseline_row(
        bucket_id="baseline_random_entry_null",
        name="Random-entry/null baseline",
        baseline_id="random_entry",
        rows=rows,
        evidence_path=evidence,
    )
    random_row = rows.get("random_entry", {})
    if random_bucket["status"] == PASS and random_row.get("candidate_beats_random_median") is False:
        random_bucket["status"] = FAIL
        random_bucket["pass"] = False
        random_bucket["reason"] = "candidate does not beat random-entry median"
    buckets.append(random_bucket)

    buckets.append(
        _classify_baseline_row(
            bucket_id="baseline_simple_trend",
            name="Simple trend baseline",
            baseline_id="simple_trend",
            rows=rows,
            evidence_path=evidence,
        )
    )
    buckets.append(
        _classify_baseline_row(
            bucket_id="baseline_simple_mean_reversion",
            name="Simple mean-reversion baseline",
            baseline_id="simple_mean_reversion",
            rows=rows,
            evidence_path=evidence,
        )
    )
    buckets.append(
        _classify_baseline_row(
            bucket_id="baseline_simple_carry_term_structure",
            name="Simple carry/term-structure baseline",
            baseline_id="simple_carry",
            rows=rows,
            evidence_path=evidence,
        )
    )
    return buckets


def _required_checks(
    statistical_validity: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
) -> Mapping[str, Mapping[str, Any]]:
    checks = statistical_validity.get("required_checks")
    if isinstance(checks, Mapping) and checks:
        return {
            str(key): value
            for key, value in checks.items()
            if isinstance(value, Mapping)
        }
    phase8_checks = _nested_mapping(phase8_decision, "statistical_validity_gate", "check_results")
    return {
        str(key): value
        for key, value in phase8_checks.items()
        if isinstance(value, Mapping)
    }


def _classify_required_check(
    *,
    bucket_id: str,
    name: str,
    check_keys: Sequence[str],
    checks: Mapping[str, Mapping[str, Any]],
    evidence_path: str | None,
    category: str,
) -> dict[str, Any]:
    for key in check_keys:
        row = checks.get(key)
        if not row:
            continue
        status = _status_from_raw(row.get("status"))
        return _bucket(
            bucket_id=bucket_id,
            category=category,
            name=name,
            status=status,
            reason=str(row.get("reason") or f"{key} status is {row.get('status')}"),
            evidence_paths=[evidence_path],
            details={"check_key": key, "check": dict(row)},
        )
    return _bucket(
        bucket_id=bucket_id,
        category=category,
        name=name,
        status=MISSING,
        reason=f"{name} evidence is missing",
        evidence_paths=[evidence_path],
    )


def _classify_statistical_and_nulls(
    *,
    statistical_validity: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
    statistical_path: str | None,
    phase8_path: str | None,
) -> list[dict[str, Any]]:
    checks = _required_checks(statistical_validity, phase8_decision)
    evidence = statistical_path or phase8_path
    return [
        _classify_required_check(
            bucket_id="null_label_shuffle",
            category="null",
            name="Label shuffle null",
            check_keys=("label_shuffle", "shuffled_labels", "label_randomization"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="null_timing_shift",
            category="null",
            name="Timing-shift null",
            check_keys=("timing_shift", "one_bar_shift", "feature_target_shift"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="statistical_pbo",
            category="statistical_validity",
            name="PBO",
            check_keys=("pbo", "Probability of Backtest Overfitting"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="statistical_deflated_sharpe",
            category="statistical_validity",
            name="Deflated Sharpe",
            check_keys=("deflated_sharpe", "Deflated Sharpe"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="statistical_probabilistic_sharpe",
            category="statistical_validity",
            name="Probabilistic Sharpe",
            check_keys=("probabilistic_sharpe", "Probabilistic Sharpe"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="statistical_bootstrap_ci",
            category="statistical_validity",
            name="Bootstrap confidence intervals",
            check_keys=("bootstrap_confidence_intervals", "bootstrap confidence intervals"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="statistical_multiple_testing",
            category="statistical_validity",
            name="Multiple-testing adjustment",
            check_keys=("multiple_testing_adjustment", "multiple-testing adjustment"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="stability_parameter",
            category="stability",
            name="Parameter stability",
            check_keys=("parameter_stability", "parameter stability"),
            checks=checks,
            evidence_path=evidence,
        ),
        _classify_required_check(
            bucket_id="stability_regime_breakdowns",
            category="stability",
            name="Regime breakdowns",
            check_keys=("regime_breakdowns", "regime breakdowns"),
            checks=checks,
            evidence_path=evidence,
        ),
    ]


def _promotion_blockers(phase8_decision: Mapping[str, Any]) -> list[str]:
    blockers = phase8_decision.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = []
    gate_blockers = _nested_mapping(phase8_decision, "promotion_gate").get("promotion_blockers", [])
    if isinstance(gate_blockers, list):
        blockers = [*blockers, *gate_blockers]
    return list(dict.fromkeys(str(item) for item in blockers))


def _classify_stability_scope(
    *,
    phase8_decision: Mapping[str, Any],
    phase8_path: str | None,
) -> dict[str, Any]:
    if not phase8_decision:
        return _bucket(
            bucket_id="stability_fold_market_year_session",
            category="stability",
            name="Fold/market/year/session stability",
            status=MISSING,
            reason="Phase 8 stability evidence is missing",
            evidence_paths=[phase8_path],
        )
    blockers = _promotion_blockers(phase8_decision)
    bad = [
        item
        for item in blockers
        if "nonpositive net_return_dollars for markets" in item
        or "nonpositive net_return_dollars for folds" in item
        or "regime breakdown missing" in item
    ]
    if bad:
        return _bucket(
            bucket_id="stability_fold_market_year_session",
            category="stability",
            name="Fold/market/year/session stability",
            status=FAIL,
            reason="market/fold/session/regime stability blockers are present",
            evidence_paths=[phase8_path],
            details={"blockers": bad},
        )
    if _nested_mapping(phase8_decision, "promotion_gate").get("model_promotion_allowed") is True:
        return _bucket(
            bucket_id="stability_fold_market_year_session",
            category="stability",
            name="Fold/market/year/session stability",
            status=PASS,
            reason="Phase 8 promotion gate contains no market/fold/session stability blocker",
            evidence_paths=[phase8_path],
        )
    return _bucket(
        bucket_id="stability_fold_market_year_session",
        category="stability",
        name="Fold/market/year/session stability",
        status=MISSING,
        reason="stability evidence is incomplete or not promotion-ready",
        evidence_paths=[phase8_path],
    )


def _execution_realism_subcheck(
    *,
    bucket_id: str,
    name: str,
    check_keys: Sequence[str],
    phase8_decision: Mapping[str, Any],
    phase8_path: str | None,
) -> dict[str, Any]:
    gate = phase8_decision.get("execution_realism_gate")
    if isinstance(gate, Mapping):
        checks = gate.get("check_results", gate.get("checks", {}))
        if isinstance(checks, Mapping):
            for key in check_keys:
                row = checks.get(key)
                if isinstance(row, Mapping):
                    status = _status_from_raw(row.get("status"))
                    return _bucket(
                        bucket_id=bucket_id,
                        category="execution",
                        name=name,
                        status=status,
                        reason=str(row.get("reason") or f"{key} status is {row.get('status')}"),
                        evidence_paths=[phase8_path],
                        details={"check_key": key, "check": dict(row)},
                    )
        if gate.get("status") == PASS:
            return _bucket(
                bucket_id=bucket_id,
                category="execution",
                name=name,
                status=PASS,
                reason="execution realism gate passed",
                evidence_paths=[phase8_path],
            )
    return _bucket(
        bucket_id=bucket_id,
        category="execution",
        name=name,
        status=MISSING,
        reason=f"{name} evidence is missing",
        evidence_paths=[phase8_path],
    )


def _classify_execution(
    *,
    failure_analysis: Mapping[str, Any],
    phase8_decision: Mapping[str, Any],
    failure_path: str | None,
    phase8_path: str | None,
) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    cost_gate = _nested_mapping(phase8_decision, "promotion_metric_gate", "cost_execution_stress_gate")
    if not cost_gate:
        cost_gate = _nested_mapping(failure_analysis, "cost_execution_stress_gate")
    if cost_gate:
        buckets.append(
            _bucket(
                bucket_id="execution_cost_stress",
                category="execution",
                name="Cost stress",
                status=_status_from_raw(cost_gate.get("status")),
                reason=f"cost stress gate status is {cost_gate.get('status')}",
                evidence_paths=[phase8_path or failure_path],
                details={"gate": dict(cost_gate)},
            )
        )
    else:
        blockers = _promotion_blockers(phase8_decision)
        cost_blockers = [item for item in blockers if "cost stress" in item or "2.0x cost" in item]
        buckets.append(
            _bucket(
                bucket_id="execution_cost_stress",
                category="execution",
                name="Cost stress",
                status=FAIL if cost_blockers else MISSING,
                reason="cost stress blocker is present" if cost_blockers else "cost stress evidence is missing",
                evidence_paths=[phase8_path or failure_path],
                details={"blockers": cost_blockers},
            )
        )

    buckets.append(
        _execution_realism_subcheck(
            bucket_id="execution_delay_stress",
            name="Delay stress",
            check_keys=("delay_stress", "latency_delay_stress", "one_bar_delay"),
            phase8_decision=phase8_decision,
            phase8_path=phase8_path,
        )
    )

    overall = (
        phase8_decision.get("costed_oos")
        if isinstance(phase8_decision.get("costed_oos"), Mapping)
        else failure_analysis.get("policy_metrics_overall")
    )
    gate_config = _nested_mapping(phase8_decision, "promotion_gate", "gate_config")
    turnover = _safe_float(overall.get("turnover_per_bar")) if isinstance(overall, Mapping) else None
    max_turnover = _safe_float(gate_config.get("max_turnover_per_bar")) or 0.10
    if turnover is None:
        turnover_bucket = _bucket(
            bucket_id="execution_turnover",
            category="execution",
            name="Turnover",
            status=MISSING,
            reason="turnover evidence is missing",
            evidence_paths=[phase8_path or failure_path],
        )
    elif turnover > max_turnover:
        turnover_bucket = _bucket(
            bucket_id="execution_turnover",
            category="execution",
            name="Turnover",
            status=FAIL,
            reason=f"turnover_per_bar {turnover} exceeds max {max_turnover}",
            evidence_paths=[phase8_path or failure_path],
            details={"turnover_per_bar": turnover, "max_turnover_per_bar": max_turnover},
        )
    else:
        turnover_bucket = _bucket(
            bucket_id="execution_turnover",
            category="execution",
            name="Turnover",
            status=PASS,
            reason="turnover is present and within the configured ceiling",
            evidence_paths=[phase8_path or failure_path],
            details={"turnover_per_bar": turnover, "max_turnover_per_bar": max_turnover},
        )
    buckets.append(turnover_bucket)

    capacity_gate = (
        failure_analysis.get("capacity_liquidity_gate")
        if isinstance(failure_analysis.get("capacity_liquidity_gate"), Mapping)
        else _nested_mapping(phase8_decision, "promotion_metric_gate", "capacity_liquidity_gate")
    )
    capacity_status = _status_from_raw(capacity_gate.get("status")) if capacity_gate else MISSING
    buckets.append(
        _bucket(
            bucket_id="execution_capacity",
            category="execution",
            name="Capacity",
            status=capacity_status,
            reason=str(
                capacity_gate.get("policy")
                or capacity_gate.get("reason")
                or "capacity evidence is missing"
            )
            if capacity_gate
            else "capacity evidence is missing",
            evidence_paths=[failure_path or phase8_path],
            details={"gate": dict(capacity_gate)} if capacity_gate else {},
        )
    )

    buckets.append(
        _execution_realism_subcheck(
            bucket_id="execution_liquidity_window",
            name="Liquidity-window",
            check_keys=("liquidity_window", "contract_liquidity_window"),
            phase8_decision=phase8_decision,
            phase8_path=phase8_path,
        )
    )
    buckets.append(
        _execution_realism_subcheck(
            bucket_id="execution_spread_slippage",
            name="Spread/slippage",
            check_keys=("spread_slippage", "bid_ask_spread", "slippage_evidence"),
            phase8_decision=phase8_decision,
            phase8_path=phase8_path,
        )
    )
    buckets.append(
        _execution_realism_subcheck(
            bucket_id="execution_partial_fills_rejects",
            name="Partial-fill/reject",
            check_keys=("partial_fills_rejects", "partial_fills", "order_rejects"),
            phase8_decision=phase8_decision,
            phase8_path=phase8_path,
        )
    )
    return buckets


def _source_summary(repo_root: Path, path: Path | None, error: str | None) -> dict[str, Any]:
    return {
        "path": _relative(repo_root, path),
        "available": error is None,
        "read_error": error,
        "sha256": _file_sha256(path),
    }


def _jsonl_count(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _registry_count(registry: Mapping[str, Any]) -> int | None:
    rows = registry.get("hypotheses")
    return len(rows) if isinstance(rows, list) else None


def _markdown(payload: Mapping[str, Any]) -> str:
    counts = payload["bucket_status_counts"]
    lines = [
        "# Alpha Evidence Gap Matrix",
        "",
        f"- run: `{payload['run_id']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- alpha_evidence_ready: `{payload['alpha_evidence_ready']}`",
        f"- bucket_status_counts: `{dict(counts)}`",
        "",
        "## Evidence Buckets",
        "",
        "| category | bucket | status | reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["buckets"]:
        reason = str(row["reason"]).replace("|", "/")
        lines.append(f"| {row['category']} | {row['bucket_id']} | {row['status']} | {reason} |")
    lines.extend(
        [
            "",
            "## Non Approval",
            "",
            "- This report does not approve target discovery, WFA/modeling, Phase 8 promotion, artifact freeze, final holdout, paper trading, live trading, provider downloads, cleanup, staging, commits, or pushes.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_alpha_evidence_gap_matrix(
    *,
    repo_root: Path,
    run_id: str = DEFAULT_RUN,
    phase8_decision_path: Path = DEFAULT_PHASE8_DECISION,
    failure_analysis_path: Path = DEFAULT_FAILURE_ANALYSIS,
    statistical_validity_path: Path = DEFAULT_STATISTICAL_VALIDITY,
    experiment_ledger_path: Path = DEFAULT_EXPERIMENT_LEDGER,
    hypothesis_registry_path: Path = DEFAULT_HYPOTHESIS_REGISTRY,
    costs_config_path: Path = DEFAULT_COSTS_CONFIG,
    models_config_path: Path = DEFAULT_MODELS_CONFIG,
    profile_config_path: Path = DEFAULT_PROFILE_CONFIG,
    report_root: Path | None = None,
    generated_at_utc: str | None = None,
    write_reports: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    generated_at_utc = generated_at_utc or _utc_now()
    phase8_path = _resolve(repo_root, phase8_decision_path)
    failure_path = _resolve(repo_root, failure_analysis_path)
    statistical_path = _resolve(repo_root, statistical_validity_path)
    ledger_path = _resolve(repo_root, experiment_ledger_path)
    registry_path = _resolve(repo_root, hypothesis_registry_path)
    costs_path = _resolve(repo_root, costs_config_path)
    models_path = _resolve(repo_root, models_config_path)
    profile_path = _resolve(repo_root, profile_config_path)

    phase8, phase8_error = _read_json(phase8_path)
    failure, failure_error = _read_json(failure_path)
    statistical, statistical_error = _read_json(statistical_path)
    registry, registry_error = _read_json(registry_path)

    phase8_rel = _relative(repo_root, phase8_path)
    failure_rel = _relative(repo_root, failure_path)
    statistical_rel = _relative(repo_root, statistical_path)

    buckets = [
        *_classify_baselines(
            failure_analysis=failure,
            phase8_decision=phase8,
            failure_path=None if failure_error else failure_rel,
            phase8_path=None if phase8_error else phase8_rel,
        ),
        *_classify_statistical_and_nulls(
            statistical_validity=statistical,
            phase8_decision=phase8,
            statistical_path=None if statistical_error else statistical_rel,
            phase8_path=None if phase8_error else phase8_rel,
        ),
        _classify_stability_scope(
            phase8_decision=phase8,
            phase8_path=None if phase8_error else phase8_rel,
        ),
        *_classify_execution(
            failure_analysis=failure,
            phase8_decision=phase8,
            failure_path=None if failure_error else failure_rel,
            phase8_path=None if phase8_error else phase8_rel,
        ),
    ]
    missing_ids = sorted(set(REQUIRED_BUCKETS) - {row["bucket_id"] for row in buckets})
    if missing_ids:
        buckets.extend(
            _bucket(
                bucket_id=bucket_id,
                category="internal",
                name=bucket_id,
                status=MISSING,
                reason="required bucket was not produced by the matrix builder",
            )
            for bucket_id in missing_ids
        )

    status_counts = Counter(str(row["status"]) for row in buckets)
    alpha_ready = all(row["status"] == PASS for row in buckets)
    verdict = READY_VERDICT if alpha_ready else PAUSE_VERDICT
    report_root = _resolve(
        repo_root,
        report_root
        or Path("reports")
        / "model_trust_audit"
        / f"alpha_evidence_gap_matrix_{_timestamp_slug(generated_at_utc)}",
    )

    payload: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "git_commit": _git_commit(repo_root),
        "script_path": _relative(repo_root, Path(__file__).resolve()),
        "diagnostic_type": "alpha_evidence_gap_matrix",
        "diagnostic_only": True,
        "run_id": run_id,
        "status": "PASS_REPORT_WRITTEN",
        "alpha_evidence_ready": alpha_ready,
        "verdict": verdict,
        "required_bucket_count": len(REQUIRED_BUCKETS),
        "bucket_status_counts": dict(status_counts),
        "buckets": buckets,
        "blockers": [
            f"{row['bucket_id']}: {row['reason']}"
            for row in buckets
            if row["status"] != PASS
        ],
        "source_evidence": {
            "phase8_decision": _source_summary(repo_root, phase8_path, phase8_error),
            "failure_analysis": _source_summary(repo_root, failure_path, failure_error),
            "statistical_validity": _source_summary(repo_root, statistical_path, statistical_error),
            "experiment_ledger": {
                "path": _relative(repo_root, ledger_path),
                "available": ledger_path is not None and ledger_path.exists(),
                "line_count": _jsonl_count(ledger_path),
                "sha256": _file_sha256(ledger_path),
            },
            "hypothesis_registry": {
                **_source_summary(repo_root, registry_path, registry_error),
                "hypothesis_count": _registry_count(registry),
            },
            "costs_config": _source_summary(repo_root, costs_path, None if costs_path and costs_path.exists() else "file missing"),
            "models_config": _source_summary(repo_root, models_path, None if models_path and models_path.exists() else "file missing"),
            "profile_config": _source_summary(repo_root, profile_path, None if profile_path and profile_path.exists() else "file missing"),
        },
        "non_approval": {
            "target_discovery": False,
            "wfa_modeling": False,
            "phase8_promotion": False,
            "artifact_freeze": False,
            "final_holdout": False,
            "paper": False,
            "live": False,
            "provider_downloads": False,
            "cleanup": False,
            "staging_commit_push": False,
        },
        "recommended_next_action": (
            "Keep modeling paused and fill missing/failed baseline, null, statistical-validity, "
            "and execution-realism evidence before any new model research."
            if not alpha_ready
            else "Only proceed with a separately predeclared model-research plan."
        ),
        "outputs": {},
    }
    if write_reports:
        assert report_root is not None
        json_path = report_root / "alpha_evidence_gap_matrix.json"
        md_path = report_root / "alpha_evidence_gap_matrix.md"
        _write_json(json_path, payload)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_markdown(payload), encoding="utf-8")
        payload["outputs"] = {
            "json": _relative(repo_root, json_path),
            "markdown": _relative(repo_root, md_path),
        }
        _write_json(json_path, payload)
        md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-id", default=DEFAULT_RUN)
    parser.add_argument("--phase8-decision", default=DEFAULT_PHASE8_DECISION.as_posix())
    parser.add_argument("--failure-analysis", default=DEFAULT_FAILURE_ANALYSIS.as_posix())
    parser.add_argument("--statistical-validity", default=DEFAULT_STATISTICAL_VALIDITY.as_posix())
    parser.add_argument("--experiment-ledger", default=DEFAULT_EXPERIMENT_LEDGER.as_posix())
    parser.add_argument("--hypothesis-registry", default=DEFAULT_HYPOTHESIS_REGISTRY.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--report-root", default=None)
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Return nonzero when alpha_evidence_ready is false.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_alpha_evidence_gap_matrix(
        repo_root=Path(args.repo_root),
        run_id=args.run_id,
        phase8_decision_path=Path(args.phase8_decision),
        failure_analysis_path=Path(args.failure_analysis),
        statistical_validity_path=Path(args.statistical_validity),
        experiment_ledger_path=Path(args.experiment_ledger),
        hypothesis_registry_path=Path(args.hypothesis_registry),
        costs_config_path=Path(args.costs_config),
        models_config_path=Path(args.models_config),
        profile_config_path=Path(args.profile_config),
        report_root=Path(args.report_root) if args.report_root else None,
        write_reports=True,
    )
    print(
        f"{result['verdict']} alpha evidence gap matrix: "
        f"ready={result['alpha_evidence_ready']} "
        f"blockers={len(result['blockers'])} "
        f"report={result['outputs'].get('json')}"
    )
    if args.fail_on_not_ready and not result["alpha_evidence_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
