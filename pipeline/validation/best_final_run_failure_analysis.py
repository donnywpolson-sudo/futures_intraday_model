from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


BEST_FINAL_ANALYSIS_CSV = Path("reports/validation/best_final_run_failure_analysis.csv")
BEST_FINAL_ANALYSIS_JSON = Path("reports/validation/best_final_run_failure_analysis.json")
FINAL_GATE_PASS_RATES_CSV = Path("reports/validation/final_gate_pass_rates.csv")
FINAL_GATE_PASS_RATES_JSON = Path("reports/validation/final_gate_pass_rates.json")
FINAL_OUTLIER_IMPACT_CSV = Path("reports/validation/final_outlier_impact.csv")
FINAL_OUTLIER_IMPACT_JSON = Path("reports/validation/final_outlier_impact.json")

ANALYSIS_FIELDS = [
    "run_id", "profile", "selected_feature_count", "net_pnl", "gross_pnl", "cost_drag",
    "cost_drag_pct_of_gross", "outlier_count", "ACCEPT", "REJECT", "most_common_failed_gate",
    "failed_gate_counts", "positive_reject_count", "positive_reject_net_pnl",
    "accepted_net_pnl", "rejected_net_pnl", "best_rejected_split", "worst_rejected_split",
    "best_accepted_split", "symbol_net_pnl", "symbol_accept_counts", "conclusion",
]
PASS_RATE_FIELDS = ["run_id", "profile", "gate", "pass_count", "fail_count", "pass_rate", "failed_positive_net_count", "failed_positive_net_pnl_sum"]
OUTLIER_IMPACT_FIELDS = [
    "run_id", "profile", "outlier_count", "outlier_net_pnl", "non_outlier_net_pnl",
    "outlier_turnover", "non_outlier_turnover", "outlier_accept_count", "outlier_reject_count",
]


def write_best_final_run_failure_analysis(profile_filter: str = "tier_1_final_threshold_p999_experiment") -> dict[str, Any]:
    best = _best_available_run(profile_filter)
    run_id = str(best.get("run_id", ""))
    profile = str(best.get("profile", profile_filter))
    breakdown = _rows_for("reports/validation/final_gate_breakdown.json", run_id, profile)
    if not run_id or not breakdown:
        rows = []
        write_csv_json(rows, csv_path=BEST_FINAL_ANALYSIS_CSV, json_path=BEST_FINAL_ANALYSIS_JSON, fields=ANALYSIS_FIELDS)
        write_csv_json(rows, csv_path=FINAL_GATE_PASS_RATES_CSV, json_path=FINAL_GATE_PASS_RATES_JSON, fields=PASS_RATE_FIELDS)
        write_csv_json(rows, csv_path=FINAL_OUTLIER_IMPACT_CSV, json_path=FINAL_OUTLIER_IMPACT_JSON, fields=OUTLIER_IMPACT_FIELDS)
        return {"run_id": run_id, "rows": 0}

    failed_counts = Counter(g for r in breakdown for g in _failed_gates(r))
    accepted = [r for r in breakdown if str(r.get("acceptance_status")) == "ACCEPT"]
    rejected = [r for r in breakdown if str(r.get("acceptance_status")) == "REJECT"]
    positive_rejects = [r for r in rejected if _float(r.get("net_pnl", r.get("pnl"))) > 0]
    symbols = _rows_for("reports/validation/final_symbol_contribution.json", run_id, profile)
    symbol_net = {str(r.get("symbol")): _float(r.get("net_pnl")) for r in symbols}
    symbol_accept = {str(r.get("symbol")): int(_float(r.get("accepted"))) for r in symbols}
    analysis = {
        "run_id": run_id,
        "profile": profile,
        "selected_feature_count": int(_float(best.get("selected_feature_count"))),
        "net_pnl": _float(best.get("net_pnl")),
        "gross_pnl": _float(best.get("gross_pnl")),
        "cost_drag": _float(best.get("cost_drag")),
        "cost_drag_pct_of_gross": _float(best.get("cost_drag_pct_of_gross")),
        "outlier_count": int(_float(best.get("outlier_count"))),
        "ACCEPT": int(_float(best.get("ACCEPT"))),
        "REJECT": int(_float(best.get("REJECT"))),
        "most_common_failed_gate": failed_counts.most_common(1)[0][0] if failed_counts else "",
        "failed_gate_counts": _kv_counts(failed_counts),
        "positive_reject_count": len(positive_rejects),
        "positive_reject_net_pnl": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in positive_rejects),
        "accepted_net_pnl": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in accepted),
        "rejected_net_pnl": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in rejected),
        "best_rejected_split": _split_id(max(rejected, key=lambda r: _float(r.get("net_pnl", r.get("pnl"))), default={})),
        "worst_rejected_split": _split_id(min(rejected, key=lambda r: _float(r.get("net_pnl", r.get("pnl"))), default={})),
        "best_accepted_split": _split_id(max(accepted, key=lambda r: _float(r.get("net_pnl", r.get("pnl"))), default={})),
        "symbol_net_pnl": _kv_float(symbol_net),
        "symbol_accept_counts": _kv_counts(Counter(symbol_accept)),
        "conclusion": _conclusion(best, failed_counts),
    }
    gate_rates = _gate_pass_rates(breakdown, run_id, profile)
    outlier_impact = _outlier_impact(run_id, profile, breakdown)
    write_csv_json([analysis], csv_path=BEST_FINAL_ANALYSIS_CSV, json_path=BEST_FINAL_ANALYSIS_JSON, fields=ANALYSIS_FIELDS)
    write_csv_json(gate_rates, csv_path=FINAL_GATE_PASS_RATES_CSV, json_path=FINAL_GATE_PASS_RATES_JSON, fields=PASS_RATE_FIELDS)
    write_csv_json([outlier_impact], csv_path=FINAL_OUTLIER_IMPACT_CSV, json_path=FINAL_OUTLIER_IMPACT_JSON, fields=OUTLIER_IMPACT_FIELDS)
    return {"run_id": run_id, "analysis": analysis, "gate_rates": gate_rates, "outlier_impact": outlier_impact}


def _best_available_run(profile_filter: str) -> dict[str, Any]:
    frozen_rows = [
        r for r in read_json_rows("reports/validation/frozen_set_comparison.json")
        if str(r.get("profile")) == profile_filter and str(r.get("artifact_available")).lower() == "true"
    ]
    if frozen_rows:
        return max(frozen_rows, key=lambda r: _float(r.get("net_pnl")))
    rows = [r for r in read_json_rows("reports/validation/final_threshold_profile_comparison.json") if str(r.get("profile")) == profile_filter]
    return max(rows, key=lambda r: _float(r.get("net_pnl")), default={})


def _gate_pass_rates(breakdown: list[dict[str, Any]], run_id: str, profile: str) -> list[dict[str, Any]]:
    gates = sorted({g for r in breakdown for g in _failed_gates(r)})
    total = len(breakdown)
    rows = []
    for gate in gates:
        failed = [r for r in breakdown if gate in _failed_gates(r)]
        failed_pos = [r for r in failed if _float(r.get("net_pnl", r.get("pnl"))) > 0]
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "gate": gate,
            "pass_count": total - len(failed),
            "fail_count": len(failed),
            "pass_rate": 0.0 if total == 0 else (total - len(failed)) / total,
            "failed_positive_net_count": len(failed_pos),
            "failed_positive_net_pnl_sum": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in failed_pos),
        })
    return rows


def _outlier_impact(run_id: str, profile: str, breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    outliers = _rows_for("reports/validation/final_threshold_outliers.json", run_id, profile)
    outlier_keys = {(str(r.get("symbol")), str(r.get("split"))) for r in outliers}
    outlier_rows = [r for r in breakdown if (str(r.get("symbol")), str(r.get("split"))) in outlier_keys]
    non_outlier_rows = [r for r in breakdown if (str(r.get("symbol")), str(r.get("split"))) not in outlier_keys]
    return {
        "run_id": run_id,
        "profile": profile,
        "outlier_count": len(outlier_rows),
        "outlier_net_pnl": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in outlier_rows),
        "non_outlier_net_pnl": sum(_float(r.get("net_pnl", r.get("pnl"))) for r in non_outlier_rows),
        "outlier_turnover": sum(_float(r.get("turnover")) for r in outlier_rows),
        "non_outlier_turnover": sum(_float(r.get("turnover")) for r in non_outlier_rows),
        "outlier_accept_count": sum(1 for r in outlier_rows if str(r.get("acceptance_status")) == "ACCEPT"),
        "outlier_reject_count": sum(1 for r in outlier_rows if str(r.get("acceptance_status")) == "REJECT"),
    }


def _rows_for(path: str | Path, run_id: str, profile: str) -> list[dict[str, Any]]:
    return [r for r in read_json_rows(path) if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile]


def _failed_gates(row: dict[str, Any]) -> list[str]:
    return [g for g in str(row.get("failed_gates", "")).split(",") if g]


def _split_id(row: dict[str, Any]) -> str:
    if not row:
        return ""
    return f"{row.get('symbol')}:{row.get('split')}"


def _kv_counts(counts: Counter | dict[str, Any]) -> str:
    return ";".join(f"{k}:{int(_float(v))}" for k, v in sorted(dict(counts).items()))


def _kv_float(values: dict[str, Any]) -> str:
    return ";".join(f"{k}:{_float(v):.10g}" for k, v in sorted(values.items()))


def _conclusion(best: dict[str, Any], failed_counts: Counter) -> str:
    gate = str(best.get("final_gate_status", ""))
    if gate == "PASS":
        return "PASS_GATE_RESEARCH_READY"
    common = failed_counts.most_common(1)[0][0] if failed_counts else "unknown"
    return f"NO_DEPLOYABLE_ALPHA: Stage 27 failed; most_common_failed_gate={common}"


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
