from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


SUMMARY_CSV = Path("reports/validation/research_branch_summary.csv")
SUMMARY_JSON = Path("reports/validation/research_branch_summary.json")
SUMMARY_MD = Path("reports/validation/research_branch_summary.md")

FIELDS = [
    "run_id",
    "profile",
    "pipeline_stage_status",
    "pipeline_pass_count",
    "pipeline_fail_count",
    "pipeline_warn_count",
    "pipeline_missing_count",
    "pipeline_skipped_count",
    "best_baseline_result",
    "best_final_p999_result",
    "robust_alpha_evidence",
    "es_split_22_outlier_diagnosis",
    "failed_gates_summary",
    "final_conclusion",
    "recommended_next_research_directions",
]

RECOMMENDATIONS = [
    "target redesign",
    "richer causal feature set",
    "event/rollover/calendar anomaly filtering diagnostics",
    "symbol-universe ablation before future final WFA",
    "execution/holding-rule experiments only after robust signal evidence",
]


def write_research_branch_summary(
    *,
    final_profile: str = "tier_1_final_threshold_p999_experiment",
    final_run_id: str | None = None,
) -> dict[str, Any]:
    pipeline = read_json_rows("reports/validation/pipeline_flow_audit.json")
    baseline = _best_row(read_json_rows("reports/validation/experiment_comparison.json"), "net_pnl")
    finals = [
        r for r in read_json_rows("reports/validation/final_experiment_comparison.json")
        if str(r.get("profile")) == final_profile
    ]
    final = _best_row(finals, "net_pnl")
    if final_run_id:
        final = next((r for r in finals if str(r.get("run_id")) == final_run_id), final)
    run_id = str(final.get("run_id", final_run_id or ""))
    profile = str(final.get("profile", final_profile))
    robust = _row_for("reports/validation/robust_alpha_evidence.json", run_id, profile)
    outlier = _row_for("reports/validation/final_outlier_forensics.json", run_id, profile)
    gate_rates = _rows_for("reports/validation/final_gate_pass_rates.json", run_id, profile)
    stage_counts = Counter(str(r.get("status", "")) for r in pipeline)

    row = {
        "run_id": run_id,
        "profile": profile,
        "pipeline_stage_status": _pipeline_status_string(pipeline),
        "pipeline_pass_count": stage_counts.get("PASS", 0),
        "pipeline_fail_count": stage_counts.get("FAIL", 0),
        "pipeline_warn_count": stage_counts.get("WARN", 0),
        "pipeline_missing_count": stage_counts.get("MISSING", 0),
        "pipeline_skipped_count": stage_counts.get("SKIPPED", 0),
        "best_baseline_result": _baseline_summary(baseline),
        "best_final_p999_result": _final_summary(final),
        "robust_alpha_evidence": _robust_summary(robust),
        "es_split_22_outlier_diagnosis": _outlier_summary(outlier),
        "failed_gates_summary": _gate_summary(gate_rates),
        "final_conclusion": "NO_ROBUST_ALPHA",
        "recommended_next_research_directions": "; ".join(f"{i + 1}. {v}" for i, v in enumerate(RECOMMENDATIONS)),
    }
    write_csv_json([row], csv_path=SUMMARY_CSV, json_path=SUMMARY_JSON, fields=FIELDS)
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(_markdown(row, pipeline, gate_rates), encoding="utf-8")
    return {"row": row, "markdown": str(SUMMARY_MD)}


def _pipeline_status_string(rows: list[dict[str, Any]]) -> str:
    return "; ".join(f"{r.get('stage_index', r.get('stage'))}:{r.get('stage_name')}={r.get('status')}" for r in rows)


def _baseline_summary(row: dict[str, Any]) -> str:
    return (
        f"profile={row.get('profile','')} run_id={row.get('run_id','')} "
        f"net_pnl={_float(row.get('net_pnl')):.2f} gross_pnl={_float(row.get('gross_pnl')):.2f} "
        f"ACCEPT={int(_float(row.get('ACCEPT')))} REJECT={int(_float(row.get('REJECT')))}"
    )


def _final_summary(row: dict[str, Any]) -> str:
    return (
        f"profile={row.get('profile','')} run_id={row.get('run_id','')} "
        f"net_pnl={_float(row.get('net_pnl')):.2f} gross_pnl={_float(row.get('gross_pnl')):.2f} "
        f"cost_drag={_float(row.get('cost_drag')):.2f} outlier_count={int(_float(row.get('outlier_count')))} "
        f"ACCEPT={int(_float(row.get('ACCEPT')))} REJECT={int(_float(row.get('REJECT')))}"
    )


def _robust_summary(row: dict[str, Any]) -> str:
    return (
        f"full_net_pnl={_float(row.get('full_net_pnl')):.2f} "
        f"net_pnl_excluding_es_split_22={_float(row.get('net_pnl_excluding_es_split_22')):.2f} "
        f"net_pnl_excluding_threshold_outliers={_float(row.get('net_pnl_excluding_threshold_outliers')):.2f} "
        f"conclusion={row.get('conclusion','')}"
    )


def _outlier_summary(row: dict[str, Any]) -> str:
    return (
        f"ES split {row.get('split','22')} net_pnl={_float(row.get('net_pnl')):.2f} "
        f"top10_pct={_float(row.get('top_10_bar_pct_of_split_pnl')):.4f} "
        f"missing_bar_gaps={int(_float(row.get('missing_bar_gaps')))} "
        f"max_volume_zscore={_float(row.get('max_volume_zscore')):.2f} "
        f"failed_gates={row.get('failed_gates','')}"
    )


def _gate_summary(rows: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{r.get('gate')}:fail={int(_float(r.get('fail_count')))},pass_rate={_float(r.get('pass_rate')):.3f}"
        for r in sorted(rows, key=lambda x: _float(x.get("fail_count")), reverse=True)
    )


def _markdown(row: dict[str, Any], pipeline: list[dict[str, Any]], gate_rates: list[dict[str, Any]]) -> str:
    lines = [
        "# Research Branch Closure Summary",
        "",
        f"- run_id: `{row['run_id']}`",
        f"- profile: `{row['profile']}`",
        f"- final conclusion: `{row['final_conclusion']}`",
        "",
        "## Pipeline status",
    ]
    for r in pipeline:
        lines.append(f"- Stage {r.get('stage_index', r.get('stage'))} {r.get('stage_name')}: {r.get('status')} - {r.get('reason', '')}")
    lines += [
        "",
        "## Best baseline result",
        f"- {row['best_baseline_result']}",
        "",
        "## Best final p999 result",
        f"- {row['best_final_p999_result']}",
        "",
        "## Robust alpha evidence",
        f"- {row['robust_alpha_evidence']}",
        "",
        "## ES split 22 outlier diagnosis",
        f"- {row['es_split_22_outlier_diagnosis']}",
        "",
        "## Failed gates summary",
    ]
    for r in sorted(gate_rates, key=lambda x: _float(x.get("fail_count")), reverse=True):
        lines.append(f"- {r.get('gate')}: fail_count={r.get('fail_count')} pass_rate={_float(r.get('pass_rate')):.3f}")
    lines += [
        "",
        "## Recommended next research directions",
        *[f"{i + 1}. {v}" for i, v in enumerate(RECOMMENDATIONS)],
        "",
        "Do not claim alpha from this branch. Stage 27 rejects and robust alpha evidence is negative after excluding ES split 22.",
        "",
    ]
    return "\n".join(lines)


def _rows_for(path: str | Path, run_id: str, profile: str) -> list[dict[str, Any]]:
    return [r for r in read_json_rows(path) if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile]


def _row_for(path: str | Path, run_id: str, profile: str) -> dict[str, Any]:
    return next(iter(_rows_for(path, run_id, profile)), {})


def _best_row(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    return max(rows, key=lambda r: _float(r.get(metric)), default={})


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0

