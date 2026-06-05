from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


FROZEN_SET_COMPARISON_CSV = Path("reports/validation/frozen_set_comparison.csv")
FROZEN_SET_COMPARISON_JSON = Path("reports/validation/frozen_set_comparison.json")

FIELDS = [
    "run_id", "profile", "frozen_manifest_hash", "selected_feature_count", "selected_features",
    "gross_pnl", "net_pnl", "cost_drag", "cost_drag_pct_of_gross", "total_turnover",
    "active_splits", "median_active_bar_pct", "ACCEPT", "REJECT", "WARN", "MISSING", "outlier_count",
    "profitable_min_trades_rejects", "median_min_trades_shortfall", "best_near_miss_net_pnl",
    "best_symbol_by_net_pnl", "worst_symbol_by_net_pnl", "final_gate_status", "alpha_conclusion",
    "artifact_available", "reason_if_missing",
]


def write_frozen_set_comparison(
    *,
    current_run_id: str | None = None,
    profile_filter: str = "tier_1_final_threshold_p999_experiment",
    frozen_root: str | Path = "data/frozen_features/phase5_v1",
) -> dict[str, Any]:
    profile_rows = [
        r for r in read_json_rows("reports/validation/final_threshold_profile_comparison.json")
        if str(r.get("profile")) == profile_filter
    ]
    current_lineage = _read_json("reports/validation/stage_24_final_wfa_backtest_results.parquet.lineage.json")
    current_gate = _read_json("reports/validation/stage_27_strategy_acceptance_audit_report.json")
    selected_features = _read_selected_features(Path(frozen_root) / "feature_cols.json")
    current_run_id = str(current_run_id or current_lineage.get("run_id") or current_gate.get("run_id") or "")

    rows = []
    for row in profile_rows:
        run_id = str(row.get("run_id", ""))
        has_current_lineage = bool(current_run_id and run_id == current_run_id)
        near_miss = _best_near_miss(run_id, str(row.get("profile", ""))) if has_current_lineage else {}
        missing_reason = "" if has_current_lineage else "prior artifact unavailable; rerun old manifest only if explicitly requested"
        final_gate_status = _gate_status(current_gate) if has_current_lineage else "UNKNOWN"
        rows.append({
            "run_id": run_id,
            "profile": str(row.get("profile", "")),
            "frozen_manifest_hash": str(current_lineage.get("frozen_feature_manifest_hash", "")) if has_current_lineage else "",
            "selected_feature_count": int(_float(current_lineage.get("selected_feature_count"))) if has_current_lineage else "",
            "selected_features": ",".join(selected_features) if has_current_lineage else "",
            "gross_pnl": _float(row.get("gross_pnl")),
            "net_pnl": _float(row.get("net_pnl")),
            "cost_drag": _float(row.get("cost_drag")),
            "cost_drag_pct_of_gross": _float(row.get("cost_drag_pct_of_gross")),
            "total_turnover": _float(row.get("total_turnover")),
            "active_splits": int(_float(row.get("active_splits"))),
            "median_active_bar_pct": _float(row.get("median_active_bar_pct")),
            "ACCEPT": int(_float(row.get("ACCEPT"))),
            "REJECT": int(_float(row.get("REJECT"))),
            "WARN": int(_float(row.get("WARN"))),
            "MISSING": int(_float(row.get("MISSING"))),
            "outlier_count": int(_float(row.get("outlier_count"))),
            "profitable_min_trades_rejects": int(_float(row.get("profitable_min_trades_rejects"))),
            "median_min_trades_shortfall": _float(row.get("median_min_trades_shortfall")),
            "best_near_miss_net_pnl": _float(near_miss.get("net_pnl")),
            "best_symbol_by_net_pnl": str(row.get("best_symbol_by_net_pnl", "")),
            "worst_symbol_by_net_pnl": str(row.get("worst_symbol_by_net_pnl", "")),
            "final_gate_status": final_gate_status,
            "alpha_conclusion": str(row.get("conclusion", "")),
            "artifact_available": bool(has_current_lineage),
            "reason_if_missing": missing_reason,
        })
    rows.sort(key=lambda r: (str(r.get("frozen_manifest_hash") or "missing"), int(_float(r.get("selected_feature_count"))), str(r.get("run_id"))))
    write_csv_json(rows, csv_path=FROZEN_SET_COMPARISON_CSV, json_path=FROZEN_SET_COMPARISON_JSON, fields=FIELDS)
    best = max(rows, key=lambda r: _float(r.get("net_pnl")), default={})
    return {
        "rows": rows,
        "best_net_pnl_run": best.get("run_id", ""),
        "best_selected_feature_count": best.get("selected_feature_count", ""),
        "best_net_pnl": _float(best.get("net_pnl")),
        "best_gate": best.get("final_gate_status", ""),
    }


def print_frozen_set_comparison_summary(summary: dict[str, Any]) -> None:
    print(
        "[FROZEN SET COMPARISON] "
        f"best_net_pnl_run={summary.get('best_net_pnl_run', '')} "
        f"selected_features={summary.get('best_selected_feature_count', '')} "
        f"net_pnl={_float(summary.get('best_net_pnl')):.6g} "
        f"gate={summary.get('best_gate', '')}",
        flush=True,
    )


def _best_near_miss(run_id: str, profile: str) -> dict[str, Any]:
    rows = [
        r for r in read_json_rows("reports/validation/final_min_trades_near_miss.json")
        if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile
    ]
    return max(rows, key=lambda r: _float(r.get("net_pnl")), default={})


def _gate_status(gate: dict[str, Any]) -> str:
    status = str(gate.get("strategy_acceptance_status") or gate.get("status") or "")
    if status == "ACCEPT":
        return "PASS"
    if status == "REJECT":
        return "FAIL"
    return status or "UNKNOWN"


def _read_selected_features(path: Path) -> list[str]:
    payload = _read_json(path)
    return [str(x) for x in (payload.get("feature_cols") or payload.get("selected_features") or [])]


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
