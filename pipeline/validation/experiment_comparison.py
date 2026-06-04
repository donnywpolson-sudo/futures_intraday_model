from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

import polars as pl

from pipeline.validation.diagnostic_io import stringify_diagnostic_keys


COMPARISON_CSV = Path("reports/validation/experiment_comparison.csv")
COMPARISON_JSON = Path("reports/validation/experiment_comparison.json")
OUTLIERS_CSV = Path("reports/validation/threshold_outliers.csv")
OUTLIERS_JSON = Path("reports/validation/threshold_outliers.json")
SYMBOL_CONTRIBUTION_CSV = Path("reports/validation/symbol_contribution.csv")
SYMBOL_CONTRIBUTION_JSON = Path("reports/validation/symbol_contribution.json")
ACCEPTANCE_REASONS_CSV = Path("reports/validation/acceptance_reasons.csv")
ACCEPTANCE_REASONS_JSON = Path("reports/validation/acceptance_reasons.json")
COST_CONTRIBUTION_CSV = Path("reports/validation/cost_contribution.csv")
COST_CONTRIBUTION_JSON = Path("reports/validation/cost_contribution.json")
SYMBOL_ABLATION_CSV = Path("reports/validation/symbol_ablation.csv")
SYMBOL_ABLATION_JSON = Path("reports/validation/symbol_ablation.json")
GATE_NEAR_MISS_CSV = Path("reports/validation/gate_near_miss.csv")
GATE_NEAR_MISS_JSON = Path("reports/validation/gate_near_miss.json")
GATE_FAILURE_SUMMARY_CSV = Path("reports/validation/gate_failure_summary.csv")
GATE_FAILURE_SUMMARY_JSON = Path("reports/validation/gate_failure_summary.json")
THRESHOLD_USED_JSON = Path("reports/validation/threshold_used.json")

ACTIVE_PCT_LIMIT = 0.03
TURNOVER_LIMIT = 300.0

COMPARISON_FIELDS = [
    "profile", "run_id", "expected_rows", "successful", "failed",
    "ACCEPT", "REJECT", "WARN", "MISSING",
    "active_splits", "median_active_bar_pct", "mean_active_bar_pct",
    "median_turnover", "mean_turnover", "total_turnover",
    "total_turnover_excluding_outliers", "total_pnl", "total_pnl_excluding_outliers",
    "gross_pnl", "net_pnl", "median_sharpe", "mean_sharpe",
    "outlier_count", "accepted_outlier_count", "rejected_outlier_count",
    "outlier_pnl", "non_outlier_pnl", "outlier_turnover", "non_outlier_turnover",
    "outlier_pnl_pct_of_net", "outlier_turnover_pct_of_total",
    "cost_drag", "cost_drag_pct_of_gross",
    "best_symbol_by_net_pnl", "best_symbol_net_pnl",
    "worst_symbol_by_net_pnl", "worst_symbol_net_pnl",
    "best_split_by_pnl", "worst_split_by_pnl", "best_split_by_sharpe", "worst_split_by_sharpe",
]
OUTLIER_FIELDS = [
    "run_id", "profile", "symbol", "split", "train_abs_prediction_quantile",
    "long_threshold_used", "short_threshold_used", "test_active_bar_pct",
    "test_long_bars", "test_short_bars", "test_turnover",
    "pnl", "pnl_pct_of_total_net", "turnover_pct_of_total",
    "sharpe_annualized", "acceptance_status", "outlier_reason",
]
SYMBOL_CONTRIBUTION_FIELDS = [
    "run_id", "profile", "symbol", "splits", "accepted", "rejected",
    "gross_pnl", "net_pnl", "turnover", "median_sharpe", "mean_sharpe",
    "outlier_count", "outlier_pnl", "non_outlier_pnl",
]
ACCEPTANCE_REASON_FIELDS = [
    "run_id", "profile", "symbol", "split", "acceptance_status", "rejection_reason",
    "pnl", "gross_pnl", "net_pnl", "cost_drag", "sharpe_annualized", "turnover", "active_bar_pct",
]
COST_CONTRIBUTION_FIELDS = [
    "run_id", "profile", "symbol", "split", "gross_pnl", "net_pnl", "cost_drag",
    "cost_drag_pct_of_gross", "turnover", "pnl_per_turnover", "accepted", "rejected",
]
SYMBOL_ABLATION_FIELDS = [
    "run_id", "profile", "included_symbols", "excluded_symbol", "gross_pnl", "net_pnl",
    "cost_drag", "turnover", "ACCEPT", "REJECT", "median_sharpe", "mean_sharpe",
]
GATE_NEAR_MISS_FIELDS = [
    "run_id", "profile", "symbol", "split", "acceptance_status", "rejection_reason",
    "failed_gate_count", "failed_gates", "pnl", "net_pnl", "gross_pnl", "cost_drag",
    "sharpe_annualized", "turnover", "active_bar_pct", "positive_rejected",
    "failed_only_min_trades", "failed_only_max_drawdown", "failed_only_min_oos_sharpe",
    "failed_min_trades_and_profitable", "failed_drawdown_and_profitable",
]
GATE_FAILURE_SUMMARY_FIELDS = [
    "run_id", "profile", "gate", "failed_count", "failed_positive_net_count",
    "failed_positive_net_pnl_sum", "symbols_affected",
]


def write_experiment_reports(
    *,
    run_id: str,
    profile: str,
    expected_rows: int,
    verification_rows: list[dict[str, Any]],
    artifact_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    verification_rows = _scope_rows_by_run_id(verification_rows, run_id)
    artifact_rows = _scope_rows_by_run_id(artifact_rows, run_id)
    threshold_rows = [r for r in _read_json_list(THRESHOLD_USED_JSON) if str(r.get("run_id")) == str(run_id)]
    by_key = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in verification_rows}
    artifacts = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in artifact_rows}
    threshold_by_key = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in threshold_rows}
    gross_by_key = _gross_pnl_by_key(verification_rows)

    active_pcts = [_float(r.get("test_active_bar_pct")) for r in threshold_rows]
    turnovers = [_float(r.get("test_turnover")) for r in threshold_rows]
    pnl_vals = [_float(r.get("pnl")) for r in verification_rows]
    sharpe_vals = [_float(r.get("sharpe_annualized", r.get("sharpe"))) for r in verification_rows]
    counts = {"ACCEPT": 0, "REJECT": 0, "WARN": 0, "MISSING": 0}
    for row in artifact_rows:
        status = str(row.get("acceptance_status") or "MISSING")
        counts[status if status in counts else "MISSING"] += 1
    successful = sum(1 for r in artifact_rows if r.get("status") == "OK")

    outliers = []
    outlier_keys = set()
    total_turnover = sum(turnovers)
    net_pnl = sum(pnl_vals)
    for row in threshold_rows:
        key = (str(row.get("symbol")), int(row.get("split", 0)))
        active = _float(row.get("test_active_bar_pct"))
        turnover = _float(row.get("test_turnover"))
        reasons = []
        if active > ACTIVE_PCT_LIMIT:
            reasons.append("active_bar_pct")
        if turnover > TURNOVER_LIMIT:
            reasons.append("turnover")
        if not reasons:
            continue
        outlier_keys.add(key)
        vr = by_key.get(key, {})
        ar = artifacts.get(key, {})
        pnl = _float(vr.get("pnl"))
        outliers.append(
            {
                "run_id": run_id,
                "profile": profile,
                "symbol": row.get("symbol"),
                "split": row.get("split"),
                "train_abs_prediction_quantile": row.get("train_abs_prediction_quantile"),
                "long_threshold_used": row.get("long_threshold_used"),
                "short_threshold_used": row.get("short_threshold_used"),
                "test_active_bar_pct": active,
                "test_long_bars": row.get("test_long_bars"),
                "test_short_bars": row.get("test_short_bars"),
                "test_turnover": turnover,
                "pnl": pnl,
                "pnl_pct_of_total_net": _safe_div(pnl, net_pnl),
                "turnover_pct_of_total": _safe_div(turnover, total_turnover),
                "sharpe_annualized": _float(vr.get("sharpe_annualized", vr.get("sharpe"))),
                "acceptance_status": ar.get("acceptance_status", "MISSING"),
                "outlier_reason": "+".join(reasons),
            }
        )
    outlier_pnl = sum(_float(by_key.get(k, {}).get("pnl")) for k in outlier_keys)
    outlier_turnover = sum(_float(r.get("test_turnover")) for r in threshold_rows if (str(r.get("symbol")), int(r.get("split", 0))) in outlier_keys)
    gross_pnl = sum(gross_by_key.values())
    symbol_rows = _symbol_contribution_rows(
        run_id=run_id,
        profile=profile,
        verification_rows=verification_rows,
        threshold_rows=threshold_rows,
        artifact_rows=artifact_rows,
        outlier_keys=outlier_keys,
        gross_by_key=gross_by_key,
    )
    acceptance_reason_rows = _acceptance_reason_rows(
        run_id=run_id,
        profile=profile,
        by_key=by_key,
        artifacts=artifacts,
        threshold_by_key=threshold_by_key,
        gross_by_key=gross_by_key,
    )
    cost_rows = _cost_contribution_rows(
        run_id=run_id,
        profile=profile,
        by_key=by_key,
        artifacts=artifacts,
        threshold_by_key=threshold_by_key,
        gross_by_key=gross_by_key,
    )
    ablation_rows = _symbol_ablation_rows(
        run_id=run_id,
        profile=profile,
        cost_rows=cost_rows,
        by_key=by_key,
    )
    gate_near_miss_rows = _gate_near_miss_rows(
        run_id=run_id,
        profile=profile,
        by_key=by_key,
        artifacts=artifacts,
        threshold_by_key=threshold_by_key,
        gross_by_key=gross_by_key,
    )
    gate_failure_summary_rows = _gate_failure_summary_rows(gate_near_miss_rows)
    best_symbol = _best_worst_symbol(symbol_rows, best=True)
    worst_symbol = _best_worst_symbol(symbol_rows, best=False)
    comparison = {
        "profile": profile,
        "run_id": run_id,
        "expected_rows": expected_rows,
        "successful": successful,
        "failed": max(expected_rows - successful, 0),
        **counts,
        "active_splits": sum(1 for x in active_pcts if x > 0),
        "median_active_bar_pct": _median(active_pcts),
        "mean_active_bar_pct": _mean(active_pcts),
        "median_turnover": _median(turnovers),
        "mean_turnover": _mean(turnovers),
        "total_turnover": total_turnover,
        "total_turnover_excluding_outliers": total_turnover - outlier_turnover,
        "total_pnl": net_pnl,
        "total_pnl_excluding_outliers": net_pnl - outlier_pnl,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "median_sharpe": _median(sharpe_vals),
        "mean_sharpe": _mean(sharpe_vals),
        "outlier_count": len(outliers),
        "accepted_outlier_count": sum(1 for r in outliers if r.get("acceptance_status") == "ACCEPT"),
        "rejected_outlier_count": sum(1 for r in outliers if r.get("acceptance_status") == "REJECT"),
        "outlier_pnl": outlier_pnl,
        "non_outlier_pnl": net_pnl - outlier_pnl,
        "outlier_turnover": outlier_turnover,
        "non_outlier_turnover": total_turnover - outlier_turnover,
        "outlier_pnl_pct_of_net": _safe_div(outlier_pnl, net_pnl),
        "outlier_turnover_pct_of_total": _safe_div(outlier_turnover, total_turnover),
        "cost_drag": gross_pnl - net_pnl,
        "cost_drag_pct_of_gross": _safe_div(gross_pnl - net_pnl, gross_pnl),
        "best_symbol_by_net_pnl": best_symbol.get("symbol", ""),
        "best_symbol_net_pnl": best_symbol.get("net_pnl", ""),
        "worst_symbol_by_net_pnl": worst_symbol.get("symbol", ""),
        "worst_symbol_net_pnl": worst_symbol.get("net_pnl", ""),
        "best_split_by_pnl": _best_worst(verification_rows, "pnl", best=True),
        "worst_split_by_pnl": _best_worst(verification_rows, "pnl", best=False),
        "best_split_by_sharpe": _best_worst(verification_rows, "sharpe_annualized", best=True),
        "worst_split_by_sharpe": _best_worst(verification_rows, "sharpe_annualized", best=False),
    }
    _write_single(COMPARISON_CSV, COMPARISON_JSON, COMPARISON_FIELDS, comparison)
    _write_rows(OUTLIERS_CSV, OUTLIERS_JSON, OUTLIER_FIELDS, outliers)
    _write_rows(SYMBOL_CONTRIBUTION_CSV, SYMBOL_CONTRIBUTION_JSON, SYMBOL_CONTRIBUTION_FIELDS, symbol_rows)
    _write_rows(ACCEPTANCE_REASONS_CSV, ACCEPTANCE_REASONS_JSON, ACCEPTANCE_REASON_FIELDS, acceptance_reason_rows)
    _write_rows(COST_CONTRIBUTION_CSV, COST_CONTRIBUTION_JSON, COST_CONTRIBUTION_FIELDS, cost_rows)
    _write_rows(SYMBOL_ABLATION_CSV, SYMBOL_ABLATION_JSON, SYMBOL_ABLATION_FIELDS, ablation_rows)
    _write_rows(GATE_NEAR_MISS_CSV, GATE_NEAR_MISS_JSON, GATE_NEAR_MISS_FIELDS, gate_near_miss_rows)
    _write_rows(GATE_FAILURE_SUMMARY_CSV, GATE_FAILURE_SUMMARY_JSON, GATE_FAILURE_SUMMARY_FIELDS, gate_failure_summary_rows)
    return comparison, outliers


def print_threshold_outlier_summary(outliers: list[dict[str, Any]]) -> None:
    max_active = max((_float(r.get("test_active_bar_pct")) for r in outliers), default=0.0)
    max_turnover = max((_float(r.get("test_turnover")) for r in outliers), default=0.0)
    print(f"[THRESHOLD OUTLIER] count={len(outliers)} max_active_bar_pct={max_active:.6g} max_turnover={max_turnover:.6g}", flush=True)


def _write_single(csv_path: Path, json_path: Path, fields: list[str], row: dict[str, Any]) -> None:
    _write_rows(csv_path, json_path, fields, [row])


def _write_rows(csv_path: Path, json_path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [stringify_diagnostic_keys(r) for r in rows]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([stringify_diagnostic_keys({k: r.get(k, "") for k in fields}) for r in rows])
    json_path.write_text(json.dumps([stringify_diagnostic_keys({k: r.get(k, "") for k in fields}) for r in rows], indent=2, default=str), encoding="utf-8")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _scope_rows_by_run_id(rows: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("run_id") in ("", None) or str(r.get("run_id")) == str(run_id)]


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _median(vals: list[float]) -> float:
    return float(median(vals)) if vals else 0.0


def _mean(vals: list[float]) -> float:
    return float(mean(vals)) if vals else 0.0


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def _best_worst(rows: list[dict[str, Any]], field: str, *, best: bool) -> str:
    if not rows:
        return ""
    row = max(rows, key=lambda r: _float(r.get(field))) if best else min(rows, key=lambda r: _float(r.get(field)))
    return f"{row.get('symbol')}_split_{row.get('split')}"


def _sum_gross_pnl(rows: list[dict[str, Any]]) -> float:
    return sum(_gross_pnl_by_key(rows).values())


def _gross_pnl_by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, int], float]:
    out = {}
    for row in rows:
        key = (str(row.get("symbol")), int(row.get("split", 0)))
        path = row.get("path")
        if not path or not Path(path).exists():
            out[key] = _float(row.get("gross_pnl"))
            continue
        try:
            df = pl.read_parquet(path, columns=["gross_pnl"])
            out[key] = float(df["gross_pnl"].sum() or 0.0)
        except Exception:
            out[key] = _float(row.get("gross_pnl"))
    return out


def _symbol_contribution_rows(
    *,
    run_id: str,
    profile: str,
    verification_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    artifact_rows: list[dict[str, Any]],
    outlier_keys: set[tuple[str, int]],
    gross_by_key: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    symbols = sorted({
        str(r.get("symbol")) for r in [*verification_rows, *threshold_rows, *artifact_rows] if r.get("symbol") not in ("", None)
    })
    threshold_by_key = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in threshold_rows}
    artifacts_by_key = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in artifact_rows}
    rows = []
    for symbol in symbols:
        v_rows = [r for r in verification_rows if str(r.get("symbol")) == symbol]
        keys = {(symbol, int(r.get("split", 0))) for r in v_rows}
        keys |= {(symbol, int(r.get("split", 0))) for r in threshold_rows if str(r.get("symbol")) == symbol}
        keys |= {(symbol, int(r.get("split", 0))) for r in artifact_rows if str(r.get("symbol")) == symbol}
        pnl_by_key = {(str(r.get("symbol")), int(r.get("split", 0))): _float(r.get("pnl")) for r in v_rows}
        sharpe_vals = [_float(r.get("sharpe_annualized", r.get("sharpe"))) for r in v_rows]
        symbol_outlier_keys = keys & outlier_keys
        outlier_pnl = sum(pnl_by_key.get(k, 0.0) for k in symbol_outlier_keys)
        net_pnl = sum(pnl_by_key.values())
        accepted = 0
        rejected = 0
        for key in keys:
            status = str(artifacts_by_key.get(key, {}).get("acceptance_status") or "")
            accepted += int(status == "ACCEPT")
            rejected += int(status == "REJECT")
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": symbol,
            "splits": len(keys),
            "accepted": accepted,
            "rejected": rejected,
            "gross_pnl": sum(gross_by_key.get(k, 0.0) for k in keys),
            "net_pnl": net_pnl,
            "turnover": sum(_float(threshold_by_key.get(k, {}).get("test_turnover")) for k in keys),
            "median_sharpe": _median(sharpe_vals),
            "mean_sharpe": _mean(sharpe_vals),
            "outlier_count": len(symbol_outlier_keys),
            "outlier_pnl": outlier_pnl,
            "non_outlier_pnl": net_pnl - outlier_pnl,
        })
    return rows


def _best_worst_symbol(rows: list[dict[str, Any]], *, best: bool) -> dict[str, Any]:
    if not rows:
        return {}
    return max(rows, key=lambda r: _float(r.get("net_pnl"))) if best else min(rows, key=lambda r: _float(r.get("net_pnl")))


def _acceptance_failure_reason(path_value: Any, status: str) -> str:
    failed = _acceptance_failed_gates(path_value, status)
    if status != "REJECT":
        return ""
    return "+".join(failed) if failed else "missing_acceptance_report"


def _acceptance_failed_gates(path_value: Any, status: str) -> list[str]:
    if status != "REJECT":
        return []
    path = Path(str(path_value)) if path_value else None
    report = _read_json_dict(path) if path else {}
    gates = report.get("gates") if isinstance(report, dict) else None
    if not isinstance(gates, list):
        return []
    return [str(g.get("name")) for g in gates if isinstance(g, dict) and g.get("status") == "FAIL"]


def _all_keys(*maps: dict[tuple[str, int], Any]) -> list[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for m in maps:
        keys |= set(m.keys())
    return sorted(keys, key=lambda x: (x[0], x[1]))


def _acceptance_reason_rows(
    *,
    run_id: str,
    profile: str,
    by_key: dict[tuple[str, int], dict[str, Any]],
    artifacts: dict[tuple[str, int], dict[str, Any]],
    threshold_by_key: dict[tuple[str, int], dict[str, Any]],
    gross_by_key: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    rows = []
    for key in _all_keys(by_key, artifacts, threshold_by_key):
        vr = by_key.get(key, {})
        ar = artifacts.get(key, {})
        tr = threshold_by_key.get(key, {})
        status = str(ar.get("acceptance_status") or "MISSING")
        gross = gross_by_key.get(key, _float(vr.get("gross_pnl")))
        net = _float(vr.get("pnl", vr.get("net_pnl")))
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": key[0],
            "split": key[1],
            "acceptance_status": status,
            "rejection_reason": _acceptance_failure_reason(ar.get("acceptance_report"), status),
            "pnl": net,
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": gross - net,
            "sharpe_annualized": _float(vr.get("sharpe_annualized", vr.get("sharpe"))),
            "turnover": _float(tr.get("test_turnover")),
            "active_bar_pct": _float(tr.get("test_active_bar_pct")),
        })
    return rows


def _cost_contribution_rows(
    *,
    run_id: str,
    profile: str,
    by_key: dict[tuple[str, int], dict[str, Any]],
    artifacts: dict[tuple[str, int], dict[str, Any]],
    threshold_by_key: dict[tuple[str, int], dict[str, Any]],
    gross_by_key: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    rows = []
    for key in _all_keys(by_key, artifacts, threshold_by_key):
        vr = by_key.get(key, {})
        ar = artifacts.get(key, {})
        tr = threshold_by_key.get(key, {})
        status = str(ar.get("acceptance_status") or "MISSING")
        gross = gross_by_key.get(key, _float(vr.get("gross_pnl")))
        net = _float(vr.get("pnl", vr.get("net_pnl")))
        turnover = _float(tr.get("test_turnover"))
        cost_drag = gross - net
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": key[0],
            "split": key[1],
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": cost_drag,
            "cost_drag_pct_of_gross": _safe_div(cost_drag, gross),
            "turnover": turnover,
            "pnl_per_turnover": _safe_div(net, turnover),
            "accepted": int(status == "ACCEPT"),
            "rejected": int(status == "REJECT"),
        })
    return rows


def _symbol_ablation_rows(
    *,
    run_id: str,
    profile: str,
    cost_rows: list[dict[str, Any]],
    by_key: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    symbols = sorted({str(r.get("symbol")) for r in cost_rows if r.get("symbol") not in ("", None)})
    rows = []
    for excluded in [None, *symbols]:
        included = [s for s in symbols if s != excluded]
        selected = [r for r in cost_rows if str(r.get("symbol")) in included]
        sharpe_vals = [
            _float(vr.get("sharpe_annualized", vr.get("sharpe")))
            for k, vr in by_key.items()
            if k[0] in included
        ]
        gross = sum(_float(r.get("gross_pnl")) for r in selected)
        net = sum(_float(r.get("net_pnl")) for r in selected)
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "included_symbols": ",".join(included),
            "excluded_symbol": "" if excluded is None else excluded,
            "gross_pnl": gross,
            "net_pnl": net,
            "cost_drag": gross - net,
            "turnover": sum(_float(r.get("turnover")) for r in selected),
            "ACCEPT": sum(int(_float(r.get("accepted"))) for r in selected),
            "REJECT": sum(int(_float(r.get("rejected"))) for r in selected),
            "median_sharpe": _median(sharpe_vals),
            "mean_sharpe": _mean(sharpe_vals),
        })
    return rows


def _gate_near_miss_rows(
    *,
    run_id: str,
    profile: str,
    by_key: dict[tuple[str, int], dict[str, Any]],
    artifacts: dict[tuple[str, int], dict[str, Any]],
    threshold_by_key: dict[tuple[str, int], dict[str, Any]],
    gross_by_key: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    rows = []
    for key in _all_keys(by_key, artifacts, threshold_by_key):
        vr = by_key.get(key, {})
        ar = artifacts.get(key, {})
        tr = threshold_by_key.get(key, {})
        status = str(ar.get("acceptance_status") or "MISSING")
        failed_gates = _acceptance_failed_gates(ar.get("acceptance_report"), status)
        failed_set = set(failed_gates)
        gross = gross_by_key.get(key, _float(vr.get("gross_pnl")))
        net = _float(vr.get("pnl", vr.get("net_pnl")))
        profitable = net > 0
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": key[0],
            "split": key[1],
            "acceptance_status": status,
            "rejection_reason": "+".join(failed_gates) if failed_gates else ("" if status != "REJECT" else "missing_acceptance_report"),
            "failed_gate_count": len(failed_gates),
            "failed_gates": "+".join(failed_gates),
            "pnl": net,
            "net_pnl": net,
            "gross_pnl": gross,
            "cost_drag": gross - net,
            "sharpe_annualized": _float(vr.get("sharpe_annualized", vr.get("sharpe"))),
            "turnover": _float(tr.get("test_turnover")),
            "active_bar_pct": _float(tr.get("test_active_bar_pct")),
            "positive_rejected": int(status == "REJECT" and profitable),
            "failed_only_min_trades": int(failed_set == {"min_trades"}),
            "failed_only_max_drawdown": int(failed_set == {"max_drawdown_pct"}),
            "failed_only_min_oos_sharpe": int(failed_set == {"min_oos_sharpe"}),
            "failed_min_trades_and_profitable": int("min_trades" in failed_set and profitable),
            "failed_drawdown_and_profitable": int("max_drawdown_pct" in failed_set and profitable),
        })
    return rows


def _gate_failure_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gates = sorted({g for r in rows for g in str(r.get("failed_gates") or "").split("+") if g})
    out = []
    for gate in gates:
        failed_rows = [r for r in rows if gate in {g for g in str(r.get("failed_gates") or "").split("+") if g}]
        positive_rows = [r for r in failed_rows if _float(r.get("net_pnl")) > 0]
        run_ids = sorted({str(r.get("run_id")) for r in failed_rows})
        profiles = sorted({str(r.get("profile")) for r in failed_rows})
        out.append({
            "run_id": ",".join(run_ids),
            "profile": ",".join(profiles),
            "gate": gate,
            "failed_count": len(failed_rows),
            "failed_positive_net_count": len(positive_rows),
            "failed_positive_net_pnl_sum": sum(_float(r.get("net_pnl")) for r in positive_rows),
            "symbols_affected": ",".join(sorted({str(r.get("symbol")) for r in failed_rows})),
        })
    return out
