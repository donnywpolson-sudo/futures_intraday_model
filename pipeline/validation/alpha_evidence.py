from __future__ import annotations

from pathlib import Path
from statistics import mean, median
from typing import Any

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json
from pipeline.validation.experiment_comparison import _float, _gross_pnl_by_key, _safe_div


ALPHA_EVIDENCE_CSV = Path("reports/validation/alpha_evidence.csv")
ALPHA_EVIDENCE_JSON = Path("reports/validation/alpha_evidence.json")
THRESHOLD_OUTLIERS_JSON = Path("reports/validation/threshold_outliers.json")
THRESHOLD_USED_JSON = Path("reports/validation/threshold_used.json")

ALPHA_EVIDENCE_FIELDS = [
    "profile",
    "run_id",
    "stage_scope",
    "symbols",
    "splits",
    "gross_pnl",
    "net_pnl",
    "cost_drag",
    "cost_drag_pct_of_gross",
    "gross_sharpe",
    "net_sharpe",
    "ic_median",
    "ic_mean",
    "turnover",
    "active_bar_pct",
    "ACCEPT",
    "REJECT",
    "WARN",
    "MISSING",
    "outlier_count",
    "outlier_pnl",
    "non_outlier_pnl",
    "per_symbol_net_pnl",
    "per_symbol_acceptance_count",
    "conclusion",
]


def build_alpha_evidence_row(
    *,
    run_id: str,
    profile: str,
    stage_scope: str,
    expected_rows: int,
    verification_rows: list[dict[str, Any]],
    artifact_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    verification_rows = [r for r in verification_rows if r.get("run_id") in ("", None) or str(r.get("run_id")) == str(run_id)]
    artifact_rows = [r for r in artifact_rows if r.get("run_id") in ("", None) or str(r.get("run_id")) == str(run_id)]
    gross_by_key = _gross_pnl_by_key(verification_rows)
    net_by_key = {(str(r.get("symbol")), int(r.get("split", 0))): _float(r.get("pnl", r.get("net_pnl"))) for r in verification_rows}
    gross_pnl = sum(gross_by_key.values())
    net_pnl = sum(net_by_key.values())
    sharpe_vals = [_float(r.get("sharpe_annualized", r.get("sharpe"))) for r in verification_rows]
    ic_vals = [_float(r.get("ic")) for r in verification_rows if r.get("ic") not in ("", None)]
    counts = {"ACCEPT": 0, "REJECT": 0, "WARN": 0, "MISSING": 0}
    for row in artifact_rows:
        status = str(row.get("acceptance_status") or "MISSING")
        counts[status if status in counts else "MISSING"] += 1
    counts["MISSING"] += max(expected_rows - len(artifact_rows), 0)

    threshold_rows = [r for r in read_json_rows(THRESHOLD_USED_JSON) if str(r.get("run_id")) == str(run_id)]
    outliers = [r for r in read_json_rows(THRESHOLD_OUTLIERS_JSON) if str(r.get("run_id")) == str(run_id)]
    outlier_keys = {(str(r.get("symbol")), int(r.get("split", 0))) for r in outliers}
    outlier_pnl = sum(net_by_key.get(k, 0.0) for k in outlier_keys)
    symbols = sorted({str(r.get("symbol")) for r in [*verification_rows, *artifact_rows] if r.get("symbol") not in ("", None)})
    per_symbol_net = {
        s: sum(v for (symbol, _split), v in net_by_key.items() if symbol == s)
        for s in symbols
    }
    per_symbol_acceptance = {}
    for symbol in symbols:
        c = {"ACCEPT": 0, "REJECT": 0, "WARN": 0, "MISSING": 0}
        for row in artifact_rows:
            if str(row.get("symbol")) != symbol:
                continue
            status = str(row.get("acceptance_status") or "MISSING")
            c[status if status in c else "MISSING"] += 1
        per_symbol_acceptance[symbol] = c

    row = {
        "profile": profile,
        "run_id": run_id,
        "stage_scope": stage_scope,
        "symbols": ",".join(symbols),
        "splits": str(len({int(r.get("split", 0)) for r in verification_rows if r.get("split") not in ("", None)})),
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "cost_drag": gross_pnl - net_pnl,
        "cost_drag_pct_of_gross": _safe_div(gross_pnl - net_pnl, gross_pnl),
        "gross_sharpe": "",
        "net_sharpe": _mean(sharpe_vals),
        "ic_median": _median(ic_vals),
        "ic_mean": _mean(ic_vals),
        "turnover": sum(_float(r.get("test_turnover")) for r in threshold_rows),
        "active_bar_pct": _mean([_float(r.get("test_active_bar_pct")) for r in threshold_rows]),
        **counts,
        "outlier_count": len(outliers),
        "outlier_pnl": outlier_pnl,
        "non_outlier_pnl": net_pnl - outlier_pnl,
        "per_symbol_net_pnl": "|".join(f"{s}:{per_symbol_net[s]:.6f}" for s in symbols),
        "per_symbol_acceptance_count": "|".join(
            f"{s}:A{per_symbol_acceptance[s]['ACCEPT']}/R{per_symbol_acceptance[s]['REJECT']}/W{per_symbol_acceptance[s]['WARN']}/M{per_symbol_acceptance[s]['MISSING']}"
            for s in symbols
        ),
    }
    row["conclusion"] = _conclusion(counts, net_pnl)
    return row


def write_alpha_evidence_report(**kwargs: Any) -> dict[str, Any]:
    row = build_alpha_evidence_row(**kwargs)
    write_csv_json([row], csv_path=ALPHA_EVIDENCE_CSV, json_path=ALPHA_EVIDENCE_JSON, fields=ALPHA_EVIDENCE_FIELDS)
    return row


def _conclusion(counts: dict[str, int], net_pnl: float) -> str:
    if counts.get("ACCEPT", 0) <= 0:
        return "WEAK_ALPHA_RESEARCH_ONLY" if net_pnl > 0 else "NO_ALPHA_FOUND"
    if counts.get("REJECT", 0) or counts.get("WARN", 0) or counts.get("MISSING", 0):
        return "PROMISING_NEEDS_MORE_TESTS"
    return "PASS_GATE_RESEARCH_READY" if net_pnl > 0 else "NO_ALPHA_FOUND"


def _median(vals: list[float]) -> float:
    return float(median(vals)) if vals else 0.0


def _mean(vals: list[float]) -> float:
    return float(mean(vals)) if vals else 0.0
