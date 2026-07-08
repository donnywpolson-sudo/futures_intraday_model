#!/usr/bin/env python3
"""Build a report-only model-trust audit for the active futures research state."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "model_trust_audit"
DEFAULT_SCOPE = "tier1_core_active"
DEFAULT_FEATURE_PLACEMENT_REPORT = Path(
    "reports/data_audit/current_state/"
    "tier1_core_phase4_self_reference_cleanup_active_placement_20260706/"
    "active_placement_report.json"
)
DEFAULT_CAUSAL_READINESS_REPORT = Path(
    "reports/data_audit/current_state/"
    "phase2_readiness_post_historical_6m_tn_exclusions_20260706/"
    "active_root_raw_to_causal_readiness_post_historical_6m_tn_exclusions.json"
)
DEFAULT_SEMANTIC_MISMATCH_REPORT = Path(
    "reports/data_audit/wfa_research/tier1_rebuild_v1/metrics_artifacts/"
    "diagnostics/trend_danger_target_semantics_v1/"
    "semantic_mismatch_classification.json"
)
DEFAULT_PREDICTIONS_ROOT = Path("data/predictions")

PASS = "PASS"
FAIL = "FAIL"
WARN_RESEARCH_ONLY = "WARN_RESEARCH_ONLY"
NA_WITH_REASON = "NOT_APPLICABLE_WITH_REASON"

VERIFIED = "Verified"
INFERRED = "Inferred"
ASSUMED = "Assumed"
NOT_ESTABLISHED = "Not established"

ADMISSIBLE = "admissible"
INADMISSIBLE = "inadmissible"


METRIC_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("return", "net_return", "higher_is_better"),
    ("return", "gross_return", "higher_is_better"),
    ("return", "annualized_return", "higher_is_better"),
    ("return", "cagr", "higher_is_better"),
    ("return", "average_trade_return", "higher_is_better"),
    ("return", "median_trade_return", "higher_is_better"),
    ("risk_adjusted_return", "sharpe", "higher_is_better"),
    ("risk_adjusted_return", "sortino", "higher_is_better"),
    ("risk_adjusted_return", "calmar", "higher_is_better"),
    ("risk_adjusted_return", "profit_factor", "higher_is_better"),
    ("risk_adjusted_return", "information_ratio", "higher_is_better"),
    ("drawdown_tail_risk", "max_drawdown", "lower_is_better"),
    ("drawdown_tail_risk", "average_drawdown", "lower_is_better"),
    ("drawdown_tail_risk", "drawdown_duration", "lower_is_better"),
    ("drawdown_tail_risk", "tail_loss", "lower_is_better"),
    ("drawdown_tail_risk", "cvar", "lower_is_better"),
    ("drawdown_tail_risk", "skew", "higher_is_better"),
    ("drawdown_tail_risk", "kurtosis", "lower_is_better"),
    ("trade_quality", "hit_rate", "higher_is_better"),
    ("trade_quality", "win_loss_ratio", "higher_is_better"),
    ("trade_quality", "payoff_ratio", "higher_is_better"),
    ("trade_quality", "expectancy", "higher_is_better"),
    ("trade_quality", "average_win", "higher_is_better"),
    ("trade_quality", "average_loss", "lower_is_better"),
    ("trade_quality", "trade_count", "higher_is_better"),
    ("cost_execution", "cost_drag", "lower_is_better"),
    ("cost_execution", "spread_drag", "lower_is_better"),
    ("cost_execution", "slippage", "lower_is_better"),
    ("cost_execution", "turnover", "lower_is_better"),
    ("cost_execution", "capacity", "higher_is_better"),
    ("cost_execution", "fill_quality_evidence", "higher_is_better"),
    ("cost_execution", "rejected_partial_fill_evidence", "higher_is_better"),
    ("stability", "fold_consistency", "higher_is_better"),
    ("stability", "market_consistency", "higher_is_better"),
    ("stability", "yearly_consistency", "higher_is_better"),
    ("stability", "regime_consistency", "higher_is_better"),
    ("stability", "parameter_stability", "higher_is_better"),
    ("stability", "confidence_intervals", "higher_is_better"),
    ("statistical_validity", "pbo", "lower_is_better"),
    ("statistical_validity", "deflated_sharpe", "higher_is_better"),
    ("statistical_validity", "probabilistic_sharpe", "higher_is_better"),
    ("statistical_validity", "bootstrap_ci_support", "higher_is_better"),
    ("statistical_validity", "null_shuffle_test_result", "higher_is_better"),
    ("statistical_validity", "multiple_testing_control", "higher_is_better"),
    ("portfolio_risk", "exposure", "lower_is_better"),
    ("portfolio_risk", "leverage", "lower_is_better"),
    ("portfolio_risk", "concentration", "lower_is_better"),
    ("portfolio_risk", "sector_factor_caps", "higher_is_better"),
    ("portfolio_risk", "correlation_clustering", "higher_is_better"),
    ("portfolio_risk", "margin_to_equity", "higher_is_better"),
    ("portfolio_risk", "forced_exit_liquidity", "higher_is_better"),
    ("operational_readiness", "stale_data_guard", "higher_is_better"),
    ("operational_readiness", "stale_signal_guard", "higher_is_better"),
    ("operational_readiness", "kill_switch", "higher_is_better"),
    ("operational_readiness", "reconciliation", "higher_is_better"),
    ("operational_readiness", "alerting", "higher_is_better"),
    ("operational_readiness", "rollback", "higher_is_better"),
    ("operational_readiness", "manual_override", "higher_is_better"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"missing file: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable JSON {path.as_posix()}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON root is not an object: {path.as_posix()}"
    return payload, None


def count_files(root: Path) -> int:
    if not root.exists():
        return 0
    if root.is_file():
        return 1
    return sum(1 for path in root.rglob("*") if path.is_file())


def gate(
    gate_id: int,
    name: str,
    status: str,
    evidence_label: str,
    scope: Mapping[str, Any],
    reason: str,
    evidence_paths: Iterable[str] = (),
    blockers: Iterable[Any] = (),
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "name": name,
        "status": status,
        "evidence_label": evidence_label,
        "scope": dict(scope),
        "reason": reason,
        "evidence_paths": sorted(str(path) for path in evidence_paths if str(path)),
        "blockers": list(blockers),
    }


def metric(
    group: str,
    name: str,
    direction: str,
    *,
    score: int = 0,
    raw_value: Any = None,
    evidence_label: str = NOT_ESTABLISHED,
    admissibility: str = INADMISSIBLE,
    scope: Mapping[str, Any] | None = None,
    reason: str,
) -> dict[str, Any]:
    return {
        "group": group,
        "metric": name,
        "direction": direction,
        "score_0_100": max(0, min(100, int(score))),
        "raw_value": raw_value,
        "evidence_label": evidence_label,
        "admissibility": admissibility,
        "scope": dict(scope or {}),
        "reason": reason,
    }


def _scope_from_feature_report(feature_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not feature_report:
        return {
            "profile_alias": "tier_1_core",
            "markets": ["ES", "CL", "ZN", "6E"],
            "years": [2023, 2024],
            "market_year_count": 8,
        }
    scope = feature_report.get("scope")
    if isinstance(scope, Mapping):
        return dict(scope)
    return {}


def _feature_gate(
    feature_report: Mapping[str, Any] | None,
    feature_error: str | None,
    feature_path: Path,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scope = _scope_from_feature_report(feature_report)
    if feature_error:
        return scope, gate(
            4,
            "Causality And Leakage Controls",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Active Tier 1 feature placement evidence is unavailable; labels/features cannot be trusted for WFA.",
            blockers=[feature_error],
        )
    status = str(feature_report.get("status"))
    counts = feature_report.get("active_counts") if isinstance(feature_report, Mapping) else {}
    counts = counts if isinstance(counts, Mapping) else {}
    blockers: list[str] = []
    if status != "PASS_TIER1_CORE_PHASE4_SELF_REFERENCE_CLEANUP_ACTIVE_PLACEMENT":
        blockers.append(f"unexpected feature placement status: {status}")
    if counts.get("feature_parquets_present") != counts.get("expected_feature_parquets"):
        blockers.append("feature parquet coverage does not match expected count")
    if counts.get("sidecars_present") != counts.get("expected_sidecars"):
        blockers.append("feature sidecar coverage does not match expected count")
    if counts.get("removed_features_present_in_active_feature_cols"):
        blockers.append("removed self-reference features are still present")
    if blockers:
        return scope, gate(
            4,
            "Causality And Leakage Controls",
            WARN_RESEARCH_ONLY,
            VERIFIED,
            scope,
            "Feature placement evidence exists but contains blockers.",
            [rel(feature_path, repo_root)],
            blockers,
        )
    return scope, gate(
        4,
        "Causality And Leakage Controls",
        WARN_RESEARCH_ONLY,
        VERIFIED,
        scope,
        (
            "Tier 1 core feature placement is verified for active feature files, "
            "but this command does not prove a pre-run trial packet or WFA split readiness."
        ),
        [rel(feature_path, repo_root)],
    )


def _causal_gate(
    causal_report: Mapping[str, Any] | None,
    causal_error: str | None,
    causal_path: Path,
    scope: Mapping[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    if causal_error:
        return gate(
            2,
            "Point-In-Time Data Integrity",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Current raw/causal readiness evidence is unavailable.",
            blockers=[causal_error],
        )
    summary = causal_report.get("summary") if isinstance(causal_report, Mapping) else {}
    summary = summary if isinstance(summary, Mapping) else {}
    blockers = causal_report.get("blockers") if isinstance(causal_report, Mapping) else []
    blockers = blockers if isinstance(blockers, list) else []
    status = str(summary.get("status") or causal_report.get("status"))
    if status == "PASS":
        gate_status = PASS
        reason = "Current raw/causal readiness report is PASS for its declared scope."
    else:
        gate_status = WARN_RESEARCH_ONLY
        reason = (
            "Current raw/causal readiness is not full PASS; carry blockers forward "
            "and cap audit output at research-only."
        )
    return gate(
        2,
        "Point-In-Time Data Integrity",
        gate_status,
        VERIFIED,
        {
            **dict(scope),
            "active_raw_pair_count": summary.get("active_raw_pair_count"),
            "active_causal_pair_count": summary.get("active_causal_pair_count"),
            "raw_without_causal_count": summary.get("raw_without_causal_count"),
        },
        reason,
        [rel(causal_path, repo_root)],
        blockers,
    )


def _prediction_files(predictions_root: Path) -> list[str]:
    if not predictions_root.exists():
        return []
    return sorted(path.as_posix() for path in predictions_root.rglob("*") if path.is_file())


def _build_metric_rankings(
    *,
    scope: Mapping[str, Any],
    prediction_files: list[str],
    semantic_report: Mapping[str, Any] | None,
    semantic_error: str | None,
) -> list[dict[str, Any]]:
    if prediction_files:
        base_reason = (
            "Prediction artifacts exist, but this report-only audit does not admit them "
            "without exact-scope costed OOS, trial packet, and gate evidence."
        )
        raw_trade_count: int | None = None
    else:
        base_reason = "Active prediction artifacts are absent; trading performance metrics are inadmissible."
        raw_trade_count = 0
    if semantic_report:
        base_reason += " Historical WFA metrics also have semantic mismatch diagnostics and are not current-scope model-trust evidence."
    elif semantic_error:
        base_reason += f" Historical semantic mismatch report was not available: {semantic_error}"

    rows = [
        metric(
            group,
            name,
            direction,
            raw_value=raw_trade_count if name == "trade_count" else None,
            scope=scope,
            reason=base_reason,
        )
        for group, name, direction in METRIC_CATALOG
    ]
    return sorted(rows, key=lambda row: (row["score_0_100"], row["group"], row["metric"]), reverse=True)


def determine_permitted_use_label(gates: list[Mapping[str, Any]], trial_packet: Mapping[str, Any]) -> str:
    if any(gate.get("status") == FAIL for gate in gates[:4]):
        return "reject"
    if trial_packet.get("status") != PASS:
        return "research_only"
    if any(gate.get("status") != PASS for gate in gates[:4]):
        return "research_only"
    if any(gate.get("status") != PASS for gate in gates[4:12]):
        return "wfa_ready"
    if any(gate.get("status") != PASS for gate in gates[12:]):
        return "promotion_review_ready"
    return "live_gate_ready"


def build_report(
    *,
    repo_root: Path,
    run_id: str,
    scope_name: str = DEFAULT_SCOPE,
    feature_placement_report: Path | None = None,
    causal_readiness_report: Path | None = None,
    semantic_mismatch_report: Path | None = None,
    predictions_root: Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    feature_path = resolve_path(repo_root, feature_placement_report or DEFAULT_FEATURE_PLACEMENT_REPORT)
    causal_path = resolve_path(repo_root, causal_readiness_report or DEFAULT_CAUSAL_READINESS_REPORT)
    semantic_path = resolve_path(repo_root, semantic_mismatch_report or DEFAULT_SEMANTIC_MISMATCH_REPORT)
    prediction_root = resolve_path(repo_root, predictions_root or DEFAULT_PREDICTIONS_ROOT)

    feature_report, feature_error = read_json_object(feature_path)
    causal_report, causal_error = read_json_object(causal_path)
    semantic_report, semantic_error = read_json_object(semantic_path)
    scope, gate4 = _feature_gate(feature_report, feature_error, feature_path, repo_root)
    prediction_files = _prediction_files(prediction_root)
    gates = [
        gate(
            1,
            "Economic Hypothesis",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "No active pre-registered model hypothesis was selected for this report-only audit.",
        ),
        _causal_gate(causal_report, causal_error, causal_path, scope, repo_root),
        gate(
            3,
            "Contract, Session, And Roll Handling",
            WARN_RESEARCH_ONLY,
            INFERRED,
            scope,
            (
                "DBN/raw/causal evidence exists, but this audit does not independently "
                "prove exact-scope tick value, multiplier, expiry, first-notice, last-trade, "
                "roll-window liquidity, and continuous-contract construction."
            ),
            [rel(causal_path, repo_root)] if not causal_error else [],
            [] if not causal_error else [causal_error],
        ),
        gate4,
        gate(
            5,
            "Signal And Sizing Separation",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "No current-scope signal, sizing, or position-policy evidence is present.",
        ),
        gate(
            6,
            "Portfolio Risk",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "No current-scope portfolio exposure, margin, concentration, or drawdown evidence is present.",
        ),
        gate(
            7,
            "Execution And Cost Realism",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "No exact-scope executable spread, slippage, fill, fee, capacity, or cost evidence is present.",
        ),
        gate(
            8,
            "Backtest Eligibility",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Backtest outputs are inadmissible until upstream lineage, contract, causality, and cost gates pass.",
        ),
        gate(
            9,
            "Purged WFA/OOS Validation",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Current-scope WFA/OOS predictions are absent; active predictions root contains no files.",
            blockers=[] if prediction_files else ["active prediction artifacts are absent"],
        ),
        gate(
            10,
            "Statistical Validity",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Current-scope PBO, Deflated Sharpe, Probabilistic Sharpe, CI, null/shuffle, and multiple-testing evidence is absent.",
        ),
        gate(
            11,
            "Stress Testing",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "Current-scope stress/regime testing evidence is absent.",
        ),
        gate(
            12,
            "Promotion And Retirement Rules",
            WARN_RESEARCH_ONLY,
            NOT_ESTABLISHED,
            scope,
            "No current-scope promotion, pause, resize, kill, retire, or re-research thresholds are approved.",
        ),
        gate(
            13,
            "Paper/Live Separation",
            NA_WITH_REASON,
            VERIFIED,
            scope,
            "This report-only audit makes no paper/live readiness claim.",
        ),
        gate(
            14,
            "Operational Controls",
            NA_WITH_REASON,
            VERIFIED,
            scope,
            "Operational controls are out of scope for a research-only report and cannot be used for paper/live claims.",
        ),
    ]
    trial_packet = {
        "status": WARN_RESEARCH_ONLY,
        "evidence_label": NOT_ESTABLISHED,
        "reason": "No current-scope pre-run experiment packet or append-only model trial record was found.",
    }
    metric_rankings = _build_metric_rankings(
        scope=scope,
        prediction_files=prediction_files,
        semantic_report=semantic_report,
        semantic_error=semantic_error,
    )
    permitted_use_label = determine_permitted_use_label(gates, trial_packet)
    hard_blockers = [
        "active predictions are empty",
        "no current-scope pre-run trial packet",
        "current-scope WFA/OOS and costed performance evidence absent",
    ]
    if causal_report:
        blockers = causal_report.get("blockers")
        if isinstance(blockers, list):
            hard_blockers.extend(
                str(item.get("blocker") or item) if isinstance(item, Mapping) else str(item)
                for item in blockers
            )

    return {
        "stage": STAGE,
        "run_id": run_id,
        "generated_at_utc": generated_at_utc or utc_now(),
        "scope_name": scope_name,
        "scope": scope,
        "status": "PASS_REPORT_WRITTEN",
        "permitted_use_label": permitted_use_label,
        "evidence_policy": {
            "missing_hard_blocker_default": NOT_ESTABLISHED,
            "metric_scores_do_not_raise_final_label": True,
            "paper_live_from_backtest_forbidden": True,
        },
        "trial_packet": trial_packet,
        "gates": gates,
        "metric_rankings": metric_rankings,
        "metric_group_counts": {
            group: sum(1 for row in metric_rankings if row["group"] == group)
            for group in sorted({group for group, _, _ in METRIC_CATALOG})
        },
        "hard_blockers": sorted(set(hard_blockers)),
        "source_evidence": {
            "feature_placement_report": rel(feature_path, repo_root),
            "feature_placement_report_read_error": feature_error,
            "causal_readiness_report": rel(causal_path, repo_root),
            "causal_readiness_report_read_error": causal_error,
            "semantic_mismatch_report": rel(semantic_path, repo_root),
            "semantic_mismatch_report_read_error": semantic_error,
            "predictions_root": rel(prediction_root, repo_root),
            "active_prediction_file_count": len(prediction_files),
        },
        "non_approval": {
            "provider_downloads": False,
            "data_replacement": False,
            "wfa_model_training": False,
            "prediction_generation": False,
            "promotion": False,
            "paper": False,
            "live": False,
            "cleanup": False,
            "staging_commit_push": False,
        },
        "recommended_next_action": (
            "Run the bounded report-only active Tier 1 Phase 5 WFA preflight/split-readiness "
            "check for ES,CL,ZN,6E years 2023,2024; no WFA/model training/predictions until readiness passes."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Model Trust Audit",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at UTC: `{report['generated_at_utc']}`",
        f"- Scope: `{report['scope_name']}`",
        f"- Status: `{report['status']}`",
        f"- Permitted-use label: `{report['permitted_use_label']}`",
        "",
        "## Scope",
        "",
        f"- Markets: `{','.join(str(item) for item in report['scope'].get('markets', []))}`",
        f"- Years: `{','.join(str(item) for item in report['scope'].get('years', []))}`",
        f"- Market-years: `{report['scope'].get('market_year_count')}`",
        "",
        "## Gates",
        "",
        "| gate | status | evidence | reason |",
        "| ---: | --- | --- | --- |",
    ]
    for row in report["gates"]:
        reason = str(row["reason"]).replace("|", "\\|")
        lines.append(f"| {row['gate_id']} | `{row['status']}` | `{row['evidence_label']}` | {reason} |")
    lines.extend(
        [
            "",
            "## Metric Scores",
            "",
            "| group | metric | score | admissibility | reason |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report["metric_rankings"]:
        reason = str(row["reason"]).replace("|", "\\|")
        lines.append(
            f"| `{row['group']}` | `{row['metric']}` | {row['score_0_100']} | "
            f"`{row['admissibility']}` | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Hard Blockers",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["hard_blockers"])
    lines.extend(
        [
            "",
            "## Non-Approval",
            "",
            "- This report does not approve provider downloads, data replacement, WFA/model training, prediction generation, promotion, paper trading, live trading, cleanup, staging, commits, or pushes.",
            "",
            "## Recommended Next Action",
            "",
            f"- {report['recommended_next_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], report_root: Path) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "model_trust_audit.json"
    md_path = report_root / "model_trust_audit.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--scope", default=DEFAULT_SCOPE, choices=[DEFAULT_SCOPE])
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--report-root", default=None)
    parser.add_argument("--feature-placement-report", default=str(DEFAULT_FEATURE_PLACEMENT_REPORT))
    parser.add_argument("--causal-readiness-report", default=str(DEFAULT_CAUSAL_READINESS_REPORT))
    parser.add_argument("--semantic-mismatch-report", default=str(DEFAULT_SEMANTIC_MISMATCH_REPORT))
    parser.add_argument("--predictions-root", default=str(DEFAULT_PREDICTIONS_ROOT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    run_id = args.run_id or default_run_id()
    report_root = resolve_path(repo_root, args.report_root or Path("reports/model_trust_audit") / run_id)
    report = build_report(
        repo_root=repo_root,
        run_id=run_id,
        scope_name=args.scope,
        feature_placement_report=Path(args.feature_placement_report),
        causal_readiness_report=Path(args.causal_readiness_report),
        semantic_mismatch_report=Path(args.semantic_mismatch_report),
        predictions_root=Path(args.predictions_root),
    )
    json_path, md_path = write_report(report, report_root)
    print(
        f"{STAGE} status={report['status']} permitted_use_label={report['permitted_use_label']} "
        f"scope={report['scope_name']} metrics={len(report['metric_rankings'])} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
