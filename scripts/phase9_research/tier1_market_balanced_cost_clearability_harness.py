#!/usr/bin/env python3
"""Tier 1 market-balanced feasibility harness for cost-clearable 15m moves."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.phase7_wfa.run_wfa import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_SPLIT_PLAN,
    _file_hash_map,
    _fold_masks,
    _load_market_frame,
    _relative_path,
    load_feature_cols,
)
from scripts.phase9_research.tier1_cost_clearability_event_harness import (
    BUCKETS,
    COST_COLUMN,
    DEFAULT_COSTS_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_REPORTS_ROOT,
    GROSS_COLUMN,
    LABEL_COLUMN,
    OPPORTUNITY_COLUMN,
    _baseline_scores,
    _bucket_metrics,
    _class_balance,
    _concentration,
    _event_counts,
    _fit_logistic,
    _load_split_folds,
    _parse_csv,
    _select_bucket,
    _shuffled_features,
    _source_columns,
    _stable_seed,
    _timestamp,
    apply_opportunity_labels,
    assign_fold_stages,
    load_round_turn_costs,
    non_overlapping_events,
    resolve_profile,
    select_model_features,
)


DEFAULT_RUN = "tier1_market_balanced_cost_clearability_harness"
REQUIRED_CONTROLS = (
    "random_label",
    "shuffled_feature",
    "market_year_session_baseline",
    "inverse_score",
    "pooled_score_transfer",
)


def _evaluate_score_columns(scored: pd.DataFrame, score_columns: Mapping[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for scorer, score_col in score_columns.items():
        out[scorer] = {}
        for bucket_name, fraction in BUCKETS:
            out[scorer][bucket_name] = _bucket_metrics(_select_bucket(scored, score_col, fraction))
    return out


def _pooled_transfer_score(
    *,
    fold: Mapping[str, Any],
    all_events: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
) -> np.ndarray:
    y_all = all_events[LABEL_COLUMN].astype(int)
    pooled_train_mask, _ = _fold_masks(all_events, fold, y_all)
    pooled_train = all_events.loc[pooled_train_mask].copy()
    if pooled_train.empty:
        raise ValueError("pooled-score-transfer control has empty train events")
    model = _fit_logistic(pooled_train[list(features)], pooled_train[LABEL_COLUMN].astype(int))
    return model.predict_proba(test[list(features)])[:, 1]


def _fold_result(
    *,
    fold: Mapping[str, Any],
    stage: str,
    market_events: pd.DataFrame,
    all_events: pd.DataFrame,
    features: Sequence[str],
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    fold_id = str(fold["fold_id"])
    y_market = market_events[LABEL_COLUMN].astype(int)
    train_mask, test_mask = _fold_masks(market_events, fold, y_market)
    train = market_events.loc[train_mask].copy()
    test = market_events.loc[test_mask].copy()
    if train.empty or test.empty:
        raise ValueError("empty train or test events")

    x_train = train[list(features)]
    x_test = test[list(features)]
    y_train = train[LABEL_COLUMN].astype(int)

    model = _fit_logistic(x_train, y_train)
    model_score = model.predict_proba(x_test)[:, 1]

    rng = np.random.default_rng(_stable_seed(seed, fold_id, "random_label"))
    random_y = pd.Series(rng.permutation(y_train.to_numpy()), index=y_train.index)
    random_model = _fit_logistic(x_train, random_y)
    random_score = random_model.predict_proba(x_test)[:, 1]

    shuffled_model = _fit_logistic(
        _shuffled_features(x_train, _stable_seed(seed, fold_id, "shuffled_feature")),
        y_train,
    )
    shuffled_score = shuffled_model.predict_proba(x_test)[:, 1]
    baseline_score = _baseline_scores(train, test)
    pooled_score = _pooled_transfer_score(
        fold=fold,
        all_events=all_events,
        test=test,
        features=features,
    )

    scored = test.copy()
    scored["model_score"] = model_score
    scored["random_label_score"] = random_score
    scored["shuffled_feature_score"] = shuffled_score
    scored["market_year_session_baseline_score"] = baseline_score
    scored["inverse_score"] = -model_score
    scored["pooled_score_transfer_score"] = pooled_score
    scored["fold_id"] = fold_id
    scored["stage"] = stage
    score_columns = {
        "model": "model_score",
        "random_label": "random_label_score",
        "shuffled_feature": "shuffled_feature_score",
        "market_year_session_baseline": "market_year_session_baseline_score",
        "inverse_score": "inverse_score",
        "pooled_score_transfer": "pooled_score_transfer_score",
    }
    metrics = _evaluate_score_columns(scored, score_columns)
    model_top_5 = _select_bucket(scored, "model_score", 0.05)
    result = {
        "fold_id": fold_id,
        "stage": stage,
        "market": str(fold["market"]),
        "train_event_count": int(len(train)),
        "scored_event_count": int(len(test)),
        "positive_train_rate": float(y_train.mean()) if len(y_train) else None,
        "positive_test_rate": float(test[LABEL_COLUMN].mean()) if len(test) else None,
        "bucket_metrics": metrics,
        "positive_top_5pct": bool(metrics["model"]["top_5pct"]["oracle_net_upper_bound"] > 0),
    }
    return result, model_top_5


def _market_stage_summaries(
    fold_results: Sequence[Mapping[str, Any]],
    markets: Sequence[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for market in markets:
        out[market] = {}
        for stage in ("discovery", "confirmation"):
            rows = [
                item
                for item in fold_results
                if str(item["market"]) == market and str(item["stage"]) == stage
            ]
            scorers: dict[str, Any] = {}
            for scorer in ("model", *REQUIRED_CONTROLS):
                selected = sum(
                    int(item["bucket_metrics"][scorer]["top_5pct"]["selected_event_count"])
                    for item in rows
                    if scorer in item["bucket_metrics"]
                )
                net = sum(
                    float(item["bucket_metrics"][scorer]["top_5pct"]["oracle_net_upper_bound"])
                    for item in rows
                    if scorer in item["bucket_metrics"]
                )
                scorers[scorer] = {
                    "top_5pct_selected_event_count": selected,
                    "top_5pct_oracle_net_upper_bound": net,
                    "top_5pct_oracle_net_upper_bound_per_event": (
                        float(net / selected) if selected else None
                    ),
                }
            out[market][stage] = {
                "stage": stage,
                "fold_count": len(rows),
                "scored_event_count": sum(int(item["scored_event_count"]) for item in rows),
                "positive_top_5pct_fold_count": sum(
                    1 for item in rows if item["positive_top_5pct"]
                ),
                "scorers": scorers,
            }
    return out


def _top_5_by_market(fold_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in fold_results:
        market = str(item["market"])
        bucket = item["bucket_metrics"]["model"]["top_5pct"]
        current = out.setdefault(
            market,
            {
                "selected_event_count": 0,
                "clearable_event_count": 0,
                "oracle_gross_upper_bound": 0.0,
                "oracle_cost_dollars": 0.0,
                "oracle_net_upper_bound": 0.0,
            },
        )
        current["selected_event_count"] += int(bucket["selected_event_count"])
        current["clearable_event_count"] += int(bucket["clearable_event_count"])
        current["oracle_gross_upper_bound"] += float(bucket["oracle_gross_upper_bound"])
        current["oracle_cost_dollars"] += float(bucket["oracle_cost_dollars"])
        current["oracle_net_upper_bound"] += float(bucket["oracle_net_upper_bound"])
    for item in out.values():
        selected = int(item["selected_event_count"])
        gross = float(item["oracle_gross_upper_bound"])
        item["clearable_rate"] = float(item["clearable_event_count"] / selected) if selected else None
        item["cost_drag"] = float(item["oracle_cost_dollars"] / gross) if gross > 0 else None
    return out


def _limit_events_for_selected_folds(
    events: pd.DataFrame,
    folds: Sequence[Mapping[str, Any]],
    max_events_per_market: int | None,
) -> pd.DataFrame:
    if max_events_per_market is None or events.empty:
        return events

    selected_indices: list[int] = []
    for market, group in events.groupby("market", dropna=False, sort=False):
        group = group.sort_values("target_entry_ts", kind="mergesort")
        market_folds = sorted(
            [fold for fold in folds if str(fold.get("market")) == str(market)],
            key=lambda fold: str(fold.get("test_start", fold.get("fold_id", ""))),
        )
        if not market_folds:
            selected_indices.extend(group.head(max_events_per_market).index.tolist())
            continue

        y = group[LABEL_COLUMN].astype(int)
        per_side_quota = max(1, max_events_per_market // max(1, len(market_folds) * 2))
        chosen: list[int] = []
        for fold in market_folds:
            train_mask, test_mask = _fold_masks(group, fold, y)
            train_idx = group.index[train_mask].tolist()
            test_idx = group.index[test_mask].tolist()
            chosen.extend(train_idx[-per_side_quota:])
            chosen.extend(test_idx[:per_side_quota])

        deduped = list(dict.fromkeys(chosen))
        if len(deduped) < max_events_per_market:
            chosen_set = set(deduped)
            fill = [idx for idx in group.index.tolist() if idx not in chosen_set]
            deduped.extend(fill[: max_events_per_market - len(deduped)])
        selected_indices.extend(deduped[:max_events_per_market])

    return events.loc[selected_indices].sort_values(
        ["market", "year", "target_entry_ts"], kind="mergesort"
    ).reset_index(drop=True)


def _clearable_rate_by_market(class_balance: Mapping[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for item in class_balance.get("by_market", []):
        if isinstance(item, Mapping):
            out[str(item.get("market"))] = item.get("cost_clearable_rate")
    return out


def evaluate_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    markets = list(report["scope"]["markets"])
    event_counts = report["event_counts"]["by_market"]
    fold_results = report["fold_results"]
    market_summaries = report["market_stage_summaries"]
    top_5_by_market = report["top_5_by_market"]
    concentration = report["concentration"]
    class_balance = _clearable_rate_by_market(report["class_balance"])
    failures = list(report.get("failures", []))
    gates: list[dict[str, Any]] = []

    underpowered = [
        market
        for market in markets
        if int(event_counts.get(market, 0)) < 20000
        or int(top_5_by_market.get(market, {}).get("selected_event_count", 0)) < 600
    ]
    gates.append(
        {
            "gate": "minimum_events_and_top5_by_market",
            "pass": not failures and not underpowered,
            "failure_decision": "STOP_UNDERPOWERED",
            "underpowered_markets": underpowered,
        }
    )

    control_failures: list[str] = []
    for market in markets:
        for stage in ("discovery", "confirmation"):
            scorers = market_summaries.get(market, {}).get(stage, {}).get("scorers", {})
            model_value = scorers.get("model", {}).get("top_5pct_oracle_net_upper_bound_per_event")
            for control in REQUIRED_CONTROLS:
                control_value = scorers.get(control, {}).get(
                    "top_5pct_oracle_net_upper_bound_per_event"
                )
                if model_value is None or control_value is None or model_value <= control_value:
                    control_failures.append(f"{market}:{stage}:{control}")
    gates.append(
        {
            "gate": "each_market_beats_all_controls_by_stage",
            "pass": not control_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "required_controls": list(REQUIRED_CONTROLS),
            "failures": control_failures,
        }
    )

    positive_by_market = {
        market: sum(
            1 for item in fold_results if item["market"] == market and item["positive_top_5pct"]
        )
        for market in markets
    }
    confirmation_positive_by_market = {
        market: sum(
            1
            for item in fold_results
            if item["market"] == market
            and item["stage"] == "confirmation"
            and item["positive_top_5pct"]
        )
        for market in markets
    }
    weak_positive_markets = [
        market
        for market in markets
        if positive_by_market.get(market, 0) < 10
        or confirmation_positive_by_market.get(market, 0) < 5
    ]
    gates.append(
        {
            "gate": "positive_fold_requirement_by_market",
            "pass": not weak_positive_markets,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "positive_folds_by_market": positive_by_market,
            "confirmation_positive_folds_by_market": confirmation_positive_by_market,
            "failures": weak_positive_markets,
        }
    )

    market_quality_failures: list[str] = []
    for market in markets:
        top = top_5_by_market.get(market, {})
        all_rate = class_balance.get(market)
        top_rate = top.get("clearable_rate")
        if float(top.get("oracle_net_upper_bound", 0.0)) <= 0:
            market_quality_failures.append(f"{market}:nonpositive_oracle_net")
        if top.get("cost_drag") is None or float(top["cost_drag"]) >= 0.50:
            market_quality_failures.append(f"{market}:cost_drag")
        if all_rate is None or top_rate is None or float(top_rate) <= float(all_rate):
            market_quality_failures.append(f"{market}:clearable_rate")
    gates.append(
        {
            "gate": "market_quality_requirements",
            "pass": not market_quality_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "failures": market_quality_failures,
        }
    )

    positive_net = {
        market: max(float(top_5_by_market.get(market, {}).get("oracle_net_upper_bound", 0.0)), 0.0)
        for market in markets
    }
    total_positive_net = sum(positive_net.values())
    market_shares = {
        market: (float(value / total_positive_net) if total_positive_net > 0 else None)
        for market, value in positive_net.items()
    }
    concentration_failures = [
        market
        for market, share in market_shares.items()
        if share is None or share > 0.35 or share < 0.15
    ]
    gates.append(
        {
            "gate": "market_contribution_balance",
            "pass": not concentration_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "market_shares": market_shares,
            "min_share": 0.15,
            "max_share": 0.35,
            "failures": concentration_failures,
        }
    )

    fold_hour_failures = [
        scope
        for scope in ("fold", "hour")
        if concentration.get(scope, {}).get("max_share") is None
        or float(concentration[scope]["max_share"]) > 0.25
    ]
    gates.append(
        {
            "gate": "fold_hour_concentration_limit",
            "pass": not fold_hour_failures,
            "failure_decision": "STOP_BRANCH_PERMANENTLY",
            "max_allowed_share": 0.25,
            "failures": fold_hour_failures,
        }
    )

    decision = "PASS"
    for gate in gates:
        if gate["pass"]:
            continue
        decision = str(gate["failure_decision"])
        break
    return {"decision": decision, "gates": gates}


def _build_report(
    *,
    run: str,
    scope: Mapping[str, Any],
    input_paths: Mapping[str, Any],
    input_hashes: Mapping[str, str],
    folds: Sequence[Mapping[str, Any]],
    events: pd.DataFrame,
    skipped_overlap_count: int,
    fold_results: Sequence[Mapping[str, Any]],
    top_rows: pd.DataFrame,
    failures: Sequence[str],
) -> dict[str, Any]:
    class_balance = _class_balance(events)
    report: dict[str, Any] = {
        "run": run,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_type": "phase9_market_balanced_cost_clearability_feasibility_only",
        "not_trading_model": True,
        "scope": dict(scope),
        "input_paths": dict(input_paths),
        "input_hashes": dict(input_hashes),
        "fold_list": [str(fold["fold_id"]) for fold in folds],
        "event_counts": _event_counts(events, folds),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": class_balance,
        "fold_results": list(fold_results),
        "market_stage_summaries": _market_stage_summaries(
            fold_results, list(scope["markets"])
        ),
        "top_5_by_market": _top_5_by_market(fold_results),
        "concentration": _concentration(top_rows),
        "controls": {"required": list(REQUIRED_CONTROLS)},
        "failures": list(failures),
        "do_not_do": [
            "Do not lower or relax the 35% market concentration cap.",
            "Do not treat oracle/feasibility output as executable PnL or strategy PnL.",
            "Do not tune thresholds, costs, policy gates, features, or hyperparameters.",
            "Do not use tier1_locked_baseline_20260616 predictions.",
            "Do not proceed to direction modeling or full Tier 1 WFA from this harness alone.",
        ],
    }
    gate_result = evaluate_gates(report)
    report["gates"] = gate_result["gates"]
    report["decision"] = gate_result["decision"]
    return report


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Tier 1 Market-Balanced Cost-Clearability Harness",
        "",
        f"- run: {report['run']}",
        f"- decision: {report['decision']}",
        f"- resolved_profile: {report['scope']['resolved_profile']}",
        f"- markets: {', '.join(report['scope']['markets'])}",
        f"- years: {', '.join(str(item) for item in report['scope']['years'])}",
        "- output_type: oracle/feasibility upper bounds only",
        "",
        "## Gates",
        "",
        "| gate | pass |",
        "| --- | --- |",
    ]
    for gate in report["gates"]:
        lines.append(f"| {gate['gate']} | {gate['pass']} |")
    lines.extend(
        [
            "",
            "## Market Sleeves",
            "",
            "| market | events | selected_top_5 | oracle_net | clearable_rate | cost_drag |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    event_counts = report["event_counts"]["by_market"]
    for market in report["scope"]["markets"]:
        top = report["top_5_by_market"].get(market, {})
        lines.append(
            "| {market} | {events} | {selected} | {net:.2f} | {clearable} | {cost_drag} |".format(
                market=market,
                events=int(event_counts.get(market, 0)),
                selected=int(top.get("selected_event_count", 0)),
                net=float(top.get("oracle_net_upper_bound", 0.0)),
                clearable=(
                    f"{float(top['clearable_rate']):.4f}"
                    if top.get("clearable_rate") is not None
                    else "NA"
                ),
                cost_drag=(
                    f"{float(top['cost_drag']):.4f}"
                    if top.get("cost_drag") is not None
                    else "NA"
                ),
            )
        )
    lines.extend(["", "## Do Not Do", ""])
    for item in report["do_not_do"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _write_report(report: Mapping[str, Any], reports_root: Path, run: str) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp()
    json_path = reports_root / f"{run}_{suffix}.json"
    md_path = reports_root / f"{run}_{suffix}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return md_path, json_path


def run_harness(
    *,
    run: str = DEFAULT_RUN,
    profile: str = DEFAULT_PROFILE,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    input_root: Path = DEFAULT_INPUT_ROOT,
    split_plan: Path = DEFAULT_SPLIT_PLAN,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    feature_cols_path: Path | None = None,
    fold_ids: Sequence[str] | None = None,
    max_events_per_market: int | None = None,
    seed: int = 1729,
    write_reports: bool = True,
) -> dict[str, Any]:
    scope = resolve_profile(profile_config, profile)
    costs = load_round_turn_costs(costs_config, scope["markets"])
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    model_features = select_model_features(feature_cols)
    if not model_features:
        raise SystemExit("no non-leaking model features available")
    folds, requested_folds = _load_split_folds(split_plan, scope["markets"], fold_ids)
    stages = assign_fold_stages(folds)

    all_events: list[pd.DataFrame] = []
    matrix_paths: list[Path] = []
    failures: list[str] = []
    skipped_overlap_count = 0
    for market in scope["markets"]:
        frame, load_failures, paths = _load_market_frame(
            market,
            scope["years"],
            input_root,
            _source_columns(model_features),
        )
        matrix_paths.extend(paths)
        failures.extend(load_failures)
        if frame is None:
            continue
        labeled = apply_opportunity_labels(frame, costs)
        events, skipped = non_overlapping_events(labeled)
        skipped_overlap_count += skipped
        all_events.append(events)
    if all_events:
        events = pd.concat(all_events, ignore_index=True).sort_values(
            ["market", "year", "target_entry_ts"], kind="mergesort"
        )
    else:
        events = pd.DataFrame()
    events = _limit_events_for_selected_folds(events, folds, max_events_per_market)

    fold_results: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    if not events.empty:
        for fold in folds:
            fold_id = str(fold["fold_id"])
            market = str(fold["market"])
            market_events = events[events["market"].astype(str) == market].copy()
            try:
                result, selected = _fold_result(
                    fold=fold,
                    stage=stages[fold_id],
                    market_events=market_events,
                    all_events=events,
                    features=model_features,
                    seed=seed,
                )
            except ValueError as exc:
                failures.append(f"{fold_id}: {exc}")
                continue
            fold_results.append(result)
            top_rows.append(selected)

    top_5_rows = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    input_paths = {
        "profile_config": _relative_path(profile_config),
        "costs_config": _relative_path(costs_config),
        "input_root": _relative_path(input_root),
        "feature_cols": _relative_path(resolved_feature_cols),
        "split_plan": _relative_path(split_plan),
    }
    report = _build_report(
        run=run,
        scope=scope,
        input_paths=input_paths,
        input_hashes=_file_hash_map(
            [profile_config, costs_config, resolved_feature_cols, split_plan, *matrix_paths]
        ),
        folds=folds,
        events=events,
        skipped_overlap_count=skipped_overlap_count,
        fold_results=fold_results,
        top_rows=top_5_rows,
        failures=failures,
    )
    report["model_features"] = model_features
    report["requested_fold_ids"] = requested_folds
    if write_reports:
        md_path, json_path = _write_report(report, reports_root, run)
        report["report_paths"] = {"markdown": _relative_path(md_path), "json": _relative_path(json_path)}
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--folds", default=None)
    parser.add_argument("--max-events-per-market", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1729)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = run_harness(
        run=args.run,
        profile=args.profile,
        profile_config=Path(args.profile_config),
        costs_config=Path(args.costs_config),
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        reports_root=Path(args.reports_root),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        fold_ids=_parse_csv(args.folds),
        max_events_per_market=args.max_events_per_market,
        seed=args.seed,
        write_reports=True,
    )
    print(
        f"{report['decision']} market-balanced cost-clearability harness: "
        f"run={report['run']} folds={len(report['fold_list'])} "
        f"events={sum(report['event_counts']['by_market'].values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
