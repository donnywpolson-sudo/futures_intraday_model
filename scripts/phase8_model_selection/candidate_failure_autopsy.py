#!/usr/bin/env python3
"""Build a trader-readable failed-candidate autopsy from existing artifacts."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.phase8_model_selection.analyze_trade_tick_excursions import (
    BAR_REQUIRED_COLUMNS,
    TRADE_REQUIRED_COLUMNS,
    _check_columns,
    _relative,
    _resolve,
    build_trade_excursion_frame,
    load_bars,
    load_cost_config,
)
from scripts.phase8_model_selection.evaluate_predictions import (
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _read_json,
    _relative_path,
    _write_json,
)


DEFAULT_HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
DEFAULT_RUN = "opening_range_acceptance_continuation_30m_v1_model_expansion_s1"
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_TARGET_SMOKE_ROOT = Path("reports/pipeline_audit")
DEFAULT_MARKET = "ES"
DEFAULT_YEAR = 2024
SMOKE_STAGES = ("discovery", "confirmation", "locked")
DIAGNOSTIC_TYPE = "candidate_failure_autopsy"


@dataclass(frozen=True)
class AutopsyPaths:
    target_smoke_root: Path
    wfa_manifest: Path
    wfa_report: Path
    policy_diagnostics: Path
    policy_summary: Path
    trades: Path
    bars: Path
    costs_config: Path
    first_touch_diagnostics: Path
    first_touch_grid: Path
    json_out: Path
    md_out: Path


def _run_family(run: str) -> str:
    if "_s" in run:
        prefix, suffix = run.rsplit("_s", 1)
        if suffix.isdigit():
            return prefix
    return run


def default_paths(hypothesis_id: str, run: str) -> AutopsyPaths:
    run_family = _run_family(run)
    policy_root = Path("reports/phase8_single_target_policy") / run
    first_touch_root = Path("reports/phase8_first_touch_feasibility") / run
    return AutopsyPaths(
        target_smoke_root=DEFAULT_TARGET_SMOKE_ROOT,
        wfa_manifest=Path("reports/wfa") / run_family / f"{run}_predictions_manifest.json",
        wfa_report=Path("reports/wfa") / run_family / f"{run}_wfa_report.json",
        policy_diagnostics=policy_root / f"{run}_single_target_policy_diagnostics.json",
        policy_summary=policy_root / f"{run}_single_target_policy_summary.csv",
        trades=policy_root / f"{run}_single_target_policy_trades.csv",
        bars=Path("data/feature_matrices") / f"{hypothesis_id}_wfa_smoke" / DEFAULT_MARKET / f"{DEFAULT_YEAR}.parquet",
        costs_config=DEFAULT_COSTS_CONFIG,
        first_touch_diagnostics=first_touch_root / f"{run}_first_touch_feasibility_diagnostics.json",
        first_touch_grid=first_touch_root / f"{run}_first_touch_feasibility_grid.csv",
        json_out=Path("reports/candidate_failure_autopsy") / hypothesis_id / run / "failure_autopsy.json",
        md_out=Path("docs") / f"{hypothesis_id}_failure_autopsy.md",
    )


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        missing = pd.isna(value)
    except TypeError:
        missing = False
    if isinstance(missing, bool) and missing:
        return None
    return value


def _pct(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


def _fmt_money(value: Any) -> str:
    return f"${_safe_float(value):,.2f}"


def _fmt_num(value: Any, digits: int = 2) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def _fmt_pct(rate: Any, digits: int = 1) -> str:
    return f"{100.0 * _safe_float(rate):.{digits}f}%"


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def _read_json_required(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing required {label}: {_relative(path)}")
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} is not a JSON object: {_relative(path)}")
    return payload


def _read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _read_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    _check_columns(trades, TRADE_REQUIRED_COLUMNS, "trades")
    for column in ("timestamp", "target_entry_ts", "target_exit_ts"):
        trades[column] = pd.to_datetime(trades[column], utc=True, errors="coerce")
    for column in ("year", "position"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce").astype("Int64")
    for column in ("execution_open", "execution_close", "gross_dollars", "cost_dollars", "net_dollars"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    duplicate_keys = trades.duplicated(
        ["market", "year", "timestamp", "target_entry_ts", "target_exit_ts"],
        keep=False,
    )
    if duplicate_keys.any():
        raise ValueError(f"trades contain duplicate join keys: {int(duplicate_keys.sum())}")
    return trades


def _load_target_smokes(hypothesis_id: str, root: Path) -> list[dict[str, Any]]:
    smokes: list[dict[str, Any]] = []
    for stage in SMOKE_STAGES:
        path = root / f"es_30m_target_smoke_{hypothesis_id}_{stage}_smoke.json"
        if not path.exists():
            continue
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        stage_summary = payload.get("stage_summary") or {}
        duplicate_gate = {}
        for gate in payload.get("gates") or []:
            if isinstance(gate, dict) and gate.get("gate") == "not_duplicate_of_current_15m_deadzone":
                duplicate_gate = gate
                break
        smokes.append(
            {
                "stage": stage,
                "path": _relative(path),
                "decision": payload.get("decision"),
                "failure_count": _safe_int(payload.get("failure_count")),
                "top_total_net_dollars": _safe_float(stage_summary.get("top_total_net_dollars")),
                "positive_top_net_fold_count": _safe_int(
                    stage_summary.get("positive_top_net_fold_count")
                ),
                "top_rows": _safe_int(stage_summary.get("top_rows")),
                "scored_rows": _safe_int(stage_summary.get("scored_rows")),
                "duplicate_overlap": _safe_float(duplicate_gate.get("overlap")),
            }
        )
    return smokes


def _load_policy_summary(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    summary = pd.read_csv(path)
    for column in ("trade_count", "candidate_trade_count", "blocked_by_execution_overlap", "gross_return_dollars", "cost_dollars", "net_return_dollars"):
        if column in summary.columns:
            summary[column] = pd.to_numeric(summary[column], errors="coerce")
    return summary


def _overall_policy_summary(policy_summary: pd.DataFrame | None) -> dict[str, Any] | None:
    if policy_summary is None or "scope" not in policy_summary.columns:
        return None
    overall = policy_summary.loc[policy_summary["scope"].astype(str).eq("overall")]
    if overall.empty:
        return None
    return overall.iloc[0].to_dict()


def _fold_policy_rows(policy_summary: pd.DataFrame | None) -> list[dict[str, Any]]:
    if policy_summary is None or "scope" not in policy_summary.columns:
        return []
    folds = policy_summary.loc[policy_summary["scope"].astype(str).eq("fold")].copy()
    return folds.to_dict(orient="records")


def _path_stats(paths: AutopsyPaths, market: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    if not paths.trades.exists():
        blockers.append(
            {
                "code": "MISSING_EVIDENCE",
                "evidence": _relative(paths.trades),
                "next": "Run/review the bounded costed policy diagnostic that writes the trades CSV.",
            }
        )
        return None, blockers
    if not paths.bars.exists():
        blockers.append(
            {
                "code": "MISSING_EVIDENCE",
                "evidence": _relative(paths.bars),
                "next": "Provide the materialized market-year bars used by the failed policy before reporting MFE/MAE/giveback.",
            }
        )
        return None, blockers
    try:
        costs = load_cost_config(paths.costs_config, market)
        trades = _read_trades(paths.trades)
        bars = load_bars(paths.bars)
        _check_columns(bars, BAR_REQUIRED_COLUMNS, "bars")
        frame = build_trade_excursion_frame(trades, bars, costs)
    except Exception as exc:
        blockers.append(
            {
                "code": "MISSING_EVIDENCE",
                "evidence": f"{_relative(paths.trades)} + {_relative(paths.bars)}",
                "next": f"Repair the trade/bar join before reporting path stats: {exc}",
            }
        )
        return None, blockers

    giveback = frame["favorable_excursion_ticks"] - frame["realized_gross_ticks"]
    realized_le_two = int(frame["realized_gross_ticks"].le(2).sum())
    mfe_ge_5_realized_le_2 = int(
        (frame["favorable_excursion_ticks"].ge(5) & frame["realized_gross_ticks"].le(2)).sum()
    )
    return (
        {
            "trade_count": int(len(frame)),
            "realized_gross_ticks_mean": float(frame["realized_gross_ticks"].mean()),
            "realized_gross_ticks_median": float(frame["realized_gross_ticks"].median()),
            "mfe_ticks_median": float(frame["favorable_excursion_ticks"].median()),
            "mae_ticks_median": float(frame["adverse_excursion_ticks"].median()),
            "giveback_ticks_median": float(giveback.median()),
            "realized_le_2_count": realized_le_two,
            "realized_le_2_rate": realized_le_two / len(frame) if len(frame) else 0.0,
            "mfe_ge_5_realized_le_2_count": mfe_ge_5_realized_le_2,
            "mfe_ge_5_realized_le_2_rate": (
                mfe_ge_5_realized_le_2 / len(frame) if len(frame) else 0.0
            ),
        },
        blockers,
    )


def _first_touch_summary(paths: AutopsyPaths) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    diagnostics = _read_json_optional(paths.first_touch_diagnostics)
    if diagnostics is None:
        blockers.append(
            {
                "code": "MISSING_EVIDENCE",
                "evidence": _relative(paths.first_touch_diagnostics),
                "next": "Run/review the bounded first-touch feasibility diagnostic before claiming TP/SL feasibility.",
            }
        )
        return None, blockers
    support = diagnostics.get("decision_support") or {}
    overall_rows = diagnostics.get("overall_grid_summary") or []
    best_stop_first = None
    if overall_rows:
        best_stop_first = max(
            overall_rows,
            key=lambda row: _safe_float(row.get("stop_first_net_dollars")),
        )
    return (
        {
            "screen_status": support.get("screen_status"),
            "grid_count": _safe_int(support.get("grid_count")),
            "fold_count": _safe_int(support.get("fold_count")),
            "stop_first_positive_overall_grid_count": _safe_int(
                support.get("stop_first_positive_overall_grid_count")
            ),
            "ambiguous_excluded_positive_overall_grid_count": _safe_int(
                support.get("ambiguous_excluded_positive_overall_grid_count")
            ),
            "stop_first_at_least_3_positive_fold_grid_count": _safe_int(
                support.get("stop_first_at_least_3_positive_fold_grid_count")
            ),
            "best_stop_first_cell": best_stop_first,
        },
        blockers,
    )


def _add_classification(
    rows: list[dict[str, str]],
    code: str,
    metric: str,
    explanation: str,
) -> None:
    rows.append({"code": code, "metric": metric, "explanation": explanation})


def classify_failure(
    *,
    smokes: list[dict[str, Any]],
    wfa_manifest: dict[str, Any],
    policy: dict[str, Any],
    path: dict[str, Any] | None,
    first_touch: dict[str, Any] | None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    smoke_passes = [item for item in smokes if str(item.get("decision", "")).endswith("_PASS")]
    net = _safe_float(policy.get("net_return_dollars"))
    gross = _safe_float(policy.get("gross_return_dollars"))
    costs = _safe_float(policy.get("cost_dollars"))
    trade_count = _safe_int(policy.get("trade_count"))
    candidate_count = _safe_int(policy.get("candidate_trade_count"))
    row_count = _safe_int((policy.get("coverage") or {}).get("row_count")) or _safe_int(
        wfa_manifest.get("prediction_count")
    )
    if smoke_passes and net < 0:
        _add_classification(
            rows,
            "TARGET_LOOKED_GOOD_BUT_POLICY_FAILED",
            f"{len(smoke_passes)} target-smoke pass stages, policy net {_fmt_money(net)}",
            "The target idea passed its smoke gates, but the costed policy lost money.",
        )
    if bool(policy.get("fixed_exit_policy_mismatch")) or not bool(
        (policy.get("target_policy_compatibility") or {}).get("compatible", True)
    ):
        _add_classification(
            rows,
            "TARGET_POLICY_MISMATCH",
            "target payoff basis did not match fixed-exit policy basis",
            "The label rewarded path opportunity, while the policy exited at a fixed horizon.",
        )
    if gross <= 0:
        _add_classification(
            rows,
            "GROSS_EDGE_ABSENT",
            f"gross PnL before costs {_fmt_money(gross)}",
            "The policy did not have positive dollars even before costs.",
        )
    if costs > abs(gross) and net < 0:
        _add_classification(
            rows,
            "COST_DRAG_DOMINANT",
            f"costs {_fmt_money(costs)} versus gross {_fmt_money(gross)}",
            "Execution costs were much larger than the captured gross edge.",
        )
    if row_count and candidate_count / row_count >= 0.5:
        _add_classification(
            rows,
            "OVERTRADING_OR_WEAK_FILTER",
            f"candidate trades {candidate_count}/{row_count} ({_pct(candidate_count, row_count):.1f}%)",
            "The policy wanted to trade most rows, so it had little selectivity.",
        )
    if path and _safe_float(path.get("mfe_ticks_median")) >= 5 and _safe_float(
        path.get("realized_gross_ticks_median")
    ) <= 2:
        _add_classification(
            rows,
            "PATH_OPPORTUNITY_NOT_CAPTURED",
            (
                f"median MFE {_fmt_num(path.get('mfe_ticks_median'))} ticks, "
                f"median realized {_fmt_num(path.get('realized_gross_ticks_median'))} ticks"
            ),
            "Trades often moved favorably but did not keep that value by the evaluated exit.",
        )
    if first_touch and _safe_int(first_touch.get("stop_first_positive_overall_grid_count")) == 0:
        _add_classification(
            rows,
            "FIRST_TOUCH_NO_GO",
            (
                f"positive stop-first TP/SL grids "
                f"{first_touch.get('stop_first_positive_overall_grid_count')}/{first_touch.get('grid_count')}"
            ),
            "Simple first-touch TP/SL capture did not rescue the failed policy.",
        )
    fold_nets = []
    for fold in ((policy.get("policy_metrics") or {}).get("fold") or {}).values():
        if isinstance(fold, dict):
            fold_nets.append(_safe_float(fold.get("net_return_dollars")))
    positive_folds = sum(1 for value in fold_nets if value > 0)
    if fold_nets and 0 < positive_folds < len(fold_nets):
        _add_classification(
            rows,
            "FOLD_CONCENTRATION",
            f"positive net folds {positive_folds}/{len(fold_nets)}",
            "The economic result depended on a subset of folds instead of being broad.",
        )
    if first_touch and str(first_touch.get("screen_status")) == "LOWER_TIMEFRAME_REQUIRED_AMBIGUITY_ONLY":
        _add_classification(
            rows,
            "OHLC_AMBIGUITY_REQUIRES_LOWER_TIMEFRAME",
            "first-touch screen status LOWER_TIMEFRAME_REQUIRED_AMBIGUITY_ONLY",
            "The only apparent rescue depends on same-bar ordering that OHLC cannot prove.",
        )
    return rows


def build_payload(
    *,
    hypothesis_id: str,
    run: str,
    paths: AutopsyPaths,
    market: str,
) -> dict[str, Any]:
    wfa_manifest = _read_json_required(paths.wfa_manifest, "WFA prediction manifest")
    wfa_report = _read_json_required(paths.wfa_report, "WFA report")
    policy = _read_json_required(paths.policy_diagnostics, "policy diagnostics")
    smokes = _load_target_smokes(hypothesis_id, paths.target_smoke_root)
    policy_summary = _load_policy_summary(paths.policy_summary)
    path_stats, path_blockers = _path_stats(paths, market)
    first_touch, first_touch_blockers = _first_touch_summary(paths)
    blockers = path_blockers + first_touch_blockers
    classifications = classify_failure(
        smokes=smokes,
        wfa_manifest=wfa_manifest,
        policy=policy,
        path=path_stats,
        first_touch=first_touch,
    )
    coverage = policy.get("coverage") or {}
    trade_count = _safe_int(policy.get("trade_count"))
    cost_dollars = _safe_float(policy.get("cost_dollars"))
    cost_per_trade = cost_dollars / trade_count if trade_count else 0.0
    tick_value = _safe_float(
        ((first_touch or {}).get("cost_model") or {}).get("tick_value"),
        default=0.0,
    )
    if not tick_value and path_stats:
        try:
            tick_value = load_cost_config(paths.costs_config, market).tick_value
        except Exception:
            tick_value = 0.0
    cost_ticks_per_trade = cost_per_trade / tick_value if tick_value else 0.0
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": DIAGNOSTIC_TYPE,
        "diagnostic_only": True,
        "hypothesis_id": hypothesis_id,
        "run": run,
        "promotion_allowed": False,
        "registry_status_mutation_allowed": False,
        "live_execution_ready": False,
        "failure_count": 0,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "classifications": classifications,
        "target_smokes": smokes,
        "wfa": {
            "manifest_path": _relative(paths.wfa_manifest),
            "report_path": _relative(paths.wfa_report),
            "failure_count": _safe_int(wfa_manifest.get("failure_count")),
            "prediction_count": _safe_int(wfa_manifest.get("prediction_count")),
            "fold_count": _safe_int(wfa_manifest.get("fold_count")),
            "model_ids": wfa_manifest.get("model_ids") or [],
            "target_names": wfa_manifest.get("target_names") or [],
            "prediction_markets": wfa_manifest.get("prediction_markets") or [],
            "prediction_years": wfa_manifest.get("prediction_years") or [],
            "duplicate_prediction_count": _safe_int(wfa_manifest.get("duplicate_prediction_count")),
            "artifact_evidence_ready": bool(wfa_manifest.get("artifact_evidence_ready")),
            "model_risk_gate": (wfa_report.get("model_risk_gate") or {}).get("status"),
        },
        "policy": {
            "diagnostics_path": _relative(paths.policy_diagnostics),
            "summary_path": _relative(paths.policy_summary),
            "trades_path": _relative(paths.trades),
            "failure_count": _safe_int(policy.get("failure_count")),
            "coverage": coverage,
            "trade_count": trade_count,
            "candidate_trade_count": _safe_int(policy.get("candidate_trade_count")),
            "blocked_by_execution_overlap": _safe_int(policy.get("blocked_by_execution_overlap")),
            "gross_return_dollars": _safe_float(policy.get("gross_return_dollars")),
            "cost_dollars": cost_dollars,
            "net_return_dollars": _safe_float(policy.get("net_return_dollars")),
            "cost_per_trade_dollars": cost_per_trade,
            "cost_per_trade_ticks": cost_ticks_per_trade,
            "fixed_exit_policy_mismatch": bool(policy.get("fixed_exit_policy_mismatch")),
            "target_policy_compatibility": policy.get("target_policy_compatibility") or {},
            "fold_rows": _fold_policy_rows(policy_summary),
            "overall_summary": _overall_policy_summary(policy_summary),
        },
        "path_stats": path_stats,
        "first_touch": first_touch,
        "input_file_hashes": _file_hash_map(
            [
                paths.wfa_manifest,
                paths.wfa_report,
                paths.policy_diagnostics,
                paths.policy_summary,
                paths.trades,
                paths.bars,
                paths.costs_config,
                paths.first_touch_diagnostics,
                paths.first_touch_grid,
            ]
        ),
        "json_path": _relative(paths.json_out),
        "md_path": _relative(paths.md_out),
    }
    return payload


def _timeline_rows(payload: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = []
    for smoke in payload["target_smokes"]:
        rows.append(
            [
                f"Target smoke: {smoke['stage']}",
                smoke.get("decision"),
                f"Top net {_fmt_money(smoke.get('top_total_net_dollars'))}; positive folds {smoke.get('positive_top_net_fold_count')}",
                "Target idea looked viable, not policy proof.",
            ]
        )
    wfa = payload["wfa"]
    rows.append(
        [
            "WFA/model artifacts",
            f"failure_count={wfa['failure_count']}",
            f"{wfa['prediction_count']} predictions; duplicate predictions {wfa['duplicate_prediction_count']}",
            "Prediction artifacts were mechanically usable.",
        ]
    )
    policy = payload["policy"]
    rows.append(
        [
            "Costed policy PnL",
            f"failure_count={policy['failure_count']}",
            f"net {_fmt_money(policy['net_return_dollars'])}; trades {policy['trade_count']}",
            "Economic result failed after costs.",
        ]
    )
    if payload["first_touch"]:
        first_touch = payload["first_touch"]
        rows.append(
            [
                "First-touch TP/SL feasibility",
                first_touch.get("screen_status"),
                (
                    f"positive stop-first grids "
                    f"{first_touch.get('stop_first_positive_overall_grid_count')}/{first_touch.get('grid_count')}"
                ),
                "Simple TP/SL capture did not rescue the policy.",
            ]
        )
    return rows


def _looked_good_rows(payload: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = []
    locked = next((item for item in payload["target_smokes"] if item.get("stage") == "locked"), None)
    if locked:
        rows.append(
            [
                "Locked target smoke",
                _fmt_money(locked.get("top_total_net_dollars")),
                f"{locked.get('positive_top_net_fold_count')} positive top-net folds",
                "The target contained ranked path opportunity.",
            ]
        )
        rows.append(
            [
                "Duplicate overlap",
                _fmt_num(locked.get("duplicate_overlap"), 3),
                "cap was 0.80",
                "The target was not just the existing baseline target.",
            ]
        )
    wfa = payload["wfa"]
    rows.append(
        [
            "WFA artifacts",
            f"{wfa['prediction_count']} predictions",
            f"artifact ready={wfa['artifact_evidence_ready']}",
            "The model output was clean enough to review.",
        ]
    )
    return rows


def _failed_rows(payload: dict[str, Any]) -> list[list[object]]:
    policy = payload["policy"]
    rows = [
        [
            "Gross PnL",
            _fmt_money(policy["gross_return_dollars"]),
            "Before costs",
            "The fixed-exit policy had no positive gross edge overall.",
        ],
        [
            "Costs",
            _fmt_money(policy["cost_dollars"]),
            f"{_fmt_money(policy['cost_per_trade_dollars'])}/trade",
            "The cost load overwhelmed the captured edge.",
        ],
        [
            "Net PnL",
            _fmt_money(policy["net_return_dollars"]),
            f"{policy['trade_count']} trades",
            "The executable policy failed economically.",
        ],
    ]
    if payload["first_touch"]:
        first_touch = payload["first_touch"]
        rows.append(
            [
                "First-touch TP/SL",
                f"{first_touch['stop_first_positive_overall_grid_count']}/{first_touch['grid_count']} positive grids",
                first_touch.get("screen_status"),
                "Simple TP/SL capture did not rescue the candidate.",
            ]
        )
    return rows


def _fold_rows(payload: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = []
    for fold in payload["policy"]["fold_rows"]:
        rows.append(
            [
                _coalesce(fold.get("scope_value"), fold.get("fold_id"), ""),
                _safe_int(fold.get("trade_count")),
                _fmt_money(fold.get("gross_return_dollars")),
                _fmt_money(fold.get("cost_dollars")),
                _fmt_money(fold.get("net_return_dollars")),
            ]
        )
    return rows


def build_markdown(payload: dict[str, Any]) -> str:
    hypothesis_id = payload["hypothesis_id"]
    policy = payload["policy"]
    path = payload["path_stats"]
    first_touch = payload["first_touch"]
    lines: list[str] = [
        f"# {hypothesis_id} Failure Autopsy",
        "",
        "## Summary",
        "",
        (
            "This report separates what looked promising from what failed economically. "
            "The target/model evidence can be real while the executable policy still loses money."
        ),
        "",
        "## Evidence Timeline",
        "",
    ]
    lines.extend(_markdown_table(["Layer", "Result", "Key Metric", "Plain English"], _timeline_rows(payload)))
    lines.extend(["", "## What Looked Good", ""])
    lines.extend(_markdown_table(["Evidence", "Metric", "Context", "Meaning"], _looked_good_rows(payload)))
    lines.extend(["", "## What Failed", ""])
    lines.extend(_markdown_table(["Evidence", "Metric", "Context", "Meaning"], _failed_rows(payload)))
    lines.extend(
        [
            "",
            "## Per-Trade Cost And Tick Translation",
            "",
            f"- Trades: `{policy['trade_count']}`.",
            f"- Gross PnL: `{_fmt_money(policy['gross_return_dollars'])}`.",
            f"- Costs: `{_fmt_money(policy['cost_dollars'])}` = `{_fmt_money(policy['cost_per_trade_dollars'])}` per trade.",
            f"- Cost in ticks: `{_fmt_num(policy['cost_per_trade_ticks'])}` ticks per trade.",
            f"- Net PnL: `{_fmt_money(policy['net_return_dollars'])}`.",
            "",
            "## Fixed-Exit Versus Path Opportunity",
            "",
            "The failed policy entered once and exited at the fixed horizon. It did not capture favorable path movement unless that movement was still present at the fixed exit.",
        ]
    )
    if path:
        lines.extend(
            [
                f"- Median max favorable excursion: `{_fmt_num(path['mfe_ticks_median'])}` ticks.",
                f"- Median fixed-exit realized ticks: `{_fmt_num(path['realized_gross_ticks_median'])}` ticks.",
                f"- Median giveback by fixed exit: `{_fmt_num(path['giveback_ticks_median'])}` ticks.",
                f"- Trades with MFE >= 5 ticks but realized <= 2 ticks: `{path['mfe_ge_5_realized_le_2_count']}` ({_fmt_pct(path['mfe_ge_5_realized_le_2_rate'])}).",
            ]
        )
    else:
        lines.append("- Path stats were not computed because trade/bar evidence was missing or did not join cleanly.")
    lines.extend(["", "## Fold-Level PnL", ""])
    fold_rows = _fold_rows(payload)
    if fold_rows:
        lines.extend(_markdown_table(["Fold", "Trades", "Gross", "Costs", "Net"], fold_rows))
    else:
        lines.append("- Fold-level policy summary was unavailable.")
    candidate_count = policy["candidate_trade_count"]
    row_count = _safe_int((policy.get("coverage") or {}).get("row_count"))
    lines.extend(
        [
            "",
            "## Overtrading And Turnover",
            "",
            f"- Candidate trades before non-overlap: `{candidate_count}`.",
            f"- Prediction rows: `{row_count}`.",
            f"- Candidate trade rate: `{_pct(candidate_count, row_count):.1f}%`.",
            f"- Overlap-blocked candidates: `{policy['blocked_by_execution_overlap']}`.",
            "",
            "Plain English: the model wanted to trade most rows, so the policy did not isolate a small high-quality subset.",
            "",
            "## MFE, MAE, And Giveback",
            "",
        ]
    )
    if path:
        lines.extend(
            [
                f"- Median MFE: `{_fmt_num(path['mfe_ticks_median'])}` ticks.",
                f"- Median MAE: `{_fmt_num(path['mae_ticks_median'])}` ticks.",
                f"- Median giveback: `{_fmt_num(path['giveback_ticks_median'])}` ticks.",
                f"- Realized <= 2 gross ticks: `{path['realized_le_2_count']}` ({_fmt_pct(path['realized_le_2_rate'])}).",
            ]
        )
    else:
        lines.append("- Missing evidence prevented MFE/MAE/giveback reporting.")
    lines.extend(["", "## First-Touch TP/SL Feasibility", ""])
    if first_touch:
        best = first_touch.get("best_stop_first_cell") or {}
        lines.extend(
            [
                f"- Screen status: `{first_touch['screen_status']}`.",
                f"- Positive stop-first grids: `{first_touch['stop_first_positive_overall_grid_count']}/{first_touch['grid_count']}`.",
                f"- Positive ambiguous-excluded grids: `{first_touch['ambiguous_excluded_positive_overall_grid_count']}/{first_touch['grid_count']}`.",
                f"- Best stop-first cell: TP `{best.get('take_profit_ticks')}` / SL `{best.get('stop_loss_ticks')}` with net `{_fmt_money(best.get('stop_first_net_dollars'))}`.",
            ]
        )
    else:
        lines.append("- First-touch feasibility evidence was not available.")
    lines.extend(["", "## Failure Classifications", ""])
    if payload["classifications"]:
        lines.extend(
            _markdown_table(
                ["Classification", "Trigger Metric", "Plain English"],
                [
                    [item["code"], item["metric"], item["explanation"]]
                    for item in payload["classifications"]
                ],
            )
        )
    else:
        lines.append("- No failure classification triggered from the available evidence.")
    if payload["blockers"]:
        lines.extend(["", "## Missing Evidence Blockers", ""])
        lines.extend(
            _markdown_table(
                ["Code", "Evidence", "Next Bounded Diagnostic"],
                [[item["code"], item["evidence"], item["next"]] for item in payload["blockers"]],
            )
        )
    lines.extend(
        [
            "",
            "## Trader Lesson",
            "",
            "The useful lesson is not simply that this candidate lost money. The lesson is that target quality, model classification quality, and executable policy economics are separate layers.",
            "",
            "For this candidate, the path-opportunity target looked good, but the evaluated policies did not turn that opportunity into net dollars after realistic ES costs. Future candidates should define the intended exit/capture rule at the same time as the target, then demand costed policy evidence before calling the candidate strong.",
            "",
            "This report is diagnostic only. It does not approve rescue work, parameter selection, registry/status mutation, promotion, paper trading, or live trading.",
            "",
        ]
    )
    return "\n".join(lines)


def run_autopsy(
    *,
    hypothesis_id: str,
    run: str,
    paths: AutopsyPaths,
    market: str,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    stale_outputs = [path for path in (paths.json_out, paths.md_out) if path.exists()]
    if stale_outputs and not allow_overwrite:
        rendered = ", ".join(_relative(path) for path in stale_outputs)
        raise ValueError(f"stale output path exists: {rendered}")
    payload = _json_ready(
        build_payload(
            hypothesis_id=hypothesis_id,
            run=run,
            paths=paths,
            market=market,
        )
    )
    markdown = build_markdown(payload)
    paths.json_out.parent.mkdir(parents=True, exist_ok=True)
    paths.md_out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths.json_out, payload)
    paths.md_out.write_text(markdown, encoding="utf-8")
    payload["json_output_path"] = paths.json_out
    payload["md_output_path"] = paths.md_out
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis-id", default=DEFAULT_HYPOTHESIS_ID)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--target-smoke-root", type=Path)
    parser.add_argument("--wfa-manifest", type=Path)
    parser.add_argument("--wfa-report", type=Path)
    parser.add_argument("--policy-diagnostics", type=Path)
    parser.add_argument("--policy-summary", type=Path)
    parser.add_argument("--trades", type=Path)
    parser.add_argument("--bars", type=Path)
    parser.add_argument("--costs-config", type=Path)
    parser.add_argument("--first-touch-diagnostics", type=Path)
    parser.add_argument("--first-touch-grid", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser


def _paths_from_args(args: argparse.Namespace) -> AutopsyPaths:
    defaults = default_paths(args.hypothesis_id, args.run)
    return AutopsyPaths(
        target_smoke_root=_resolve(args.target_smoke_root or defaults.target_smoke_root),
        wfa_manifest=_resolve(args.wfa_manifest or defaults.wfa_manifest),
        wfa_report=_resolve(args.wfa_report or defaults.wfa_report),
        policy_diagnostics=_resolve(args.policy_diagnostics or defaults.policy_diagnostics),
        policy_summary=_resolve(args.policy_summary or defaults.policy_summary),
        trades=_resolve(args.trades or defaults.trades),
        bars=_resolve(args.bars or defaults.bars),
        costs_config=_resolve(args.costs_config or defaults.costs_config),
        first_touch_diagnostics=_resolve(
            args.first_touch_diagnostics or defaults.first_touch_diagnostics
        ),
        first_touch_grid=_resolve(args.first_touch_grid or defaults.first_touch_grid),
        json_out=_resolve(args.json_out or defaults.json_out),
        md_out=_resolve(args.md_out or defaults.md_out),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    paths = _paths_from_args(args)
    try:
        result = run_autopsy(
            hypothesis_id=args.hypothesis_id,
            run=args.run,
            paths=paths,
            market=args.market,
            allow_overwrite=args.allow_overwrite,
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"NO_GO candidate failure autopsy: {exc}")
        return 1
    print(
        "WROTE candidate failure autopsy:",
        f"classifications={len(result['classifications'])}",
        f"blockers={result['blocker_count']}",
        f"json={_relative(result['json_output_path'])}",
        f"md={_relative(result['md_output_path'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
