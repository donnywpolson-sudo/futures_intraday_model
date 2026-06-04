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
THRESHOLD_USED_JSON = Path("reports/validation/threshold_used.json")

ACTIVE_PCT_LIMIT = 0.03
TURNOVER_LIMIT = 300.0

COMPARISON_FIELDS = [
    "profile", "run_id", "expected_rows", "successful", "failed",
    "ACCEPT", "REJECT", "WARN", "MISSING",
    "active_splits", "median_active_bar_pct", "mean_active_bar_pct",
    "median_turnover", "mean_turnover", "total_turnover",
    "gross_pnl", "net_pnl", "median_sharpe", "mean_sharpe",
    "best_split_by_pnl", "worst_split_by_pnl", "best_split_by_sharpe", "worst_split_by_sharpe",
]
OUTLIER_FIELDS = [
    "run_id", "profile", "symbol", "split", "train_abs_prediction_quantile",
    "long_threshold_used", "short_threshold_used", "test_active_bar_pct",
    "test_long_bars", "test_short_bars", "test_turnover",
    "pnl", "sharpe_annualized", "acceptance_status",
]


def write_experiment_reports(
    *,
    run_id: str,
    profile: str,
    expected_rows: int,
    verification_rows: list[dict[str, Any]],
    artifact_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    threshold_rows = [r for r in _read_json_list(THRESHOLD_USED_JSON) if str(r.get("run_id")) == str(run_id)]
    by_key = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in verification_rows}
    artifacts = {(str(r.get("symbol")), int(r.get("split", 0))): r for r in artifact_rows}

    active_pcts = [_float(r.get("test_active_bar_pct")) for r in threshold_rows]
    turnovers = [_float(r.get("test_turnover")) for r in threshold_rows]
    pnl_vals = [_float(r.get("pnl")) for r in verification_rows]
    sharpe_vals = [_float(r.get("sharpe_annualized", r.get("sharpe"))) for r in verification_rows]
    counts = {"ACCEPT": 0, "REJECT": 0, "WARN": 0, "MISSING": 0}
    for row in artifact_rows:
        status = str(row.get("acceptance_status") or "MISSING")
        counts[status if status in counts else "MISSING"] += 1
    successful = sum(1 for r in artifact_rows if r.get("status") == "OK")

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
        "total_turnover": sum(turnovers),
        "gross_pnl": _sum_gross_pnl(verification_rows),
        "net_pnl": sum(pnl_vals),
        "median_sharpe": _median(sharpe_vals),
        "mean_sharpe": _mean(sharpe_vals),
        "best_split_by_pnl": _best_worst(verification_rows, "pnl", best=True),
        "worst_split_by_pnl": _best_worst(verification_rows, "pnl", best=False),
        "best_split_by_sharpe": _best_worst(verification_rows, "sharpe_annualized", best=True),
        "worst_split_by_sharpe": _best_worst(verification_rows, "sharpe_annualized", best=False),
    }
    outliers = []
    for row in threshold_rows:
        key = (str(row.get("symbol")), int(row.get("split", 0)))
        active = _float(row.get("test_active_bar_pct"))
        turnover = _float(row.get("test_turnover"))
        if active <= ACTIVE_PCT_LIMIT and turnover <= TURNOVER_LIMIT:
            continue
        vr = by_key.get(key, {})
        ar = artifacts.get(key, {})
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
                "pnl": _float(vr.get("pnl")),
                "sharpe_annualized": _float(vr.get("sharpe_annualized", vr.get("sharpe"))),
                "acceptance_status": ar.get("acceptance_status", "MISSING"),
            }
        )
    _write_single(COMPARISON_CSV, COMPARISON_JSON, COMPARISON_FIELDS, comparison)
    _write_rows(OUTLIERS_CSV, OUTLIERS_JSON, OUTLIER_FIELDS, outliers)
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


def _best_worst(rows: list[dict[str, Any]], field: str, *, best: bool) -> str:
    if not rows:
        return ""
    row = max(rows, key=lambda r: _float(r.get(field))) if best else min(rows, key=lambda r: _float(r.get(field)))
    return f"{row.get('symbol')}_split_{row.get('split')}"


def _sum_gross_pnl(rows: list[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        path = row.get("path")
        if not path or not Path(path).exists():
            continue
        try:
            df = pl.read_parquet(path, columns=["gross_pnl"])
            total += float(df["gross_pnl"].sum() or 0.0)
        except Exception:
            continue
    return total
