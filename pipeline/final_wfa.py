from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.analytics.aggregate import compute_backtest_metrics
from pipeline.common.io_safe import atomic_write_json
from pipeline.features.frozen import validate_frozen_feature_set
from pipeline.features.preprocessing import fit_apply_train_scaler
from pipeline.gates.acceptance import run_acceptance_gate
from pipeline.modeling.full_research import _attach_execution, _feature_set_id, _fit_ridge, _predict
from pipeline.stress.stress_tests import run_stress_tests
from pipeline.validation.final_lineage import file_sha256, write_lineage
from pipeline.validation.final_gate_diagnostics import write_final_gate_diagnostics
from pipeline.validation.final_experiment_diagnostics import (
    build_final_threshold_used_row,
    update_final_threshold_profile_comparison,
    write_final_experiment_reports,
    write_final_threshold_used,
)
from pipeline.validation.final_threshold_diagnostics import write_final_threshold_diagnostics
from pipeline.validation.final_trade_audit import write_final_trade_count_audit
from pipeline.validation.frozen_set_comparison import write_frozen_set_comparison
from pipeline.validation.final_oos import (
    FINAL_OOS_PREDICTIONS,
    FINAL_WFA_BACKTEST,
    materialize_final_oos_predictions,
    validate_final_oos_predictions,
)
from pipeline.validation.threshold_used import resolve_threshold_from_train
from pipeline.walkforward.split_plan import write_wfa_split_plan
from pipeline.walkforward.walkforward import apply_walkforward_contract


STAGE26_FINAL_METRICS = Path("reports/validation/stage_26_final_metrics_diagnostics_audit_report.json")
STAGE27_FINAL_GATE = Path("reports/validation/stage_27_strategy_acceptance_audit_report.json")


def run_final_wfa_pipeline(
    *,
    config: Any,
    run_id: str,
    profile: str,
    frozen_root: str | Path = "data/frozen_features/phase5_v1",
    feature_matrix_root: str | Path = "data/feature_matrices/expanded",
) -> dict[str, Any]:
    frozen_root = Path(frozen_root)
    feature_matrix_root = Path(feature_matrix_root)
    target_col = str(getattr(getattr(config, "walkforward", object()), "walkforward_target", "target_15m_ret"))
    prereq = validate_frozen_feature_set(
        output_root=frozen_root,
        source_feature_matrix_root=feature_matrix_root,
        config=config,
    )
    if prereq.get("status") != "PASS":
        raise RuntimeError(f"FINAL WFA PREREQ FAIL: Stage 23 frozen feature set {prereq.get('status')}: {prereq.get('reason')}")

    features = _read_frozen_features(frozen_root)
    files = _scoped_feature_files(feature_matrix_root, config)
    if not files:
        raise RuntimeError(f"FINAL WFA FAIL: no expanded feature matrix parquet under {feature_matrix_root}")
    _assert_columns_available(files[0], features, target_col)

    splits = _generate_splits(files, config)
    if not splits:
        raise RuntimeError("FINAL WFA FAIL: no feasible walkforward splits")
    write_wfa_split_plan(
        splits,
        files,
        config,
        json_path="reports/wfa/final_wfa_split_plan.json",
        csv_path="reports/wfa/final_wfa_split_plan_summary.csv",
    )

    rows = []
    threshold_used_rows = []
    for split_idx, split in enumerate(splits, 1):
        train_years, test_years, train_start, train_end, test_start, test_end = _split_parts(split)
        for symbol in [str(s) for s in getattr(config, "symbols", []) or []]:
            symbol_files = [
                p for p in files
                if p.parent.name == symbol and int(p.stem) in set(train_years) | set(test_years)
            ]
            if not symbol_files:
                raise RuntimeError(f"FINAL WFA FAIL: missing files for symbol={symbol} split={split_idx}")
            result, threshold_row = _run_symbol_split(
                symbol=symbol,
                split_idx=split_idx,
                paths=symbol_files,
                features=features,
                target_col=target_col,
                config=config,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                run_id=run_id,
                profile=profile,
            )
            rows.append(result)
            threshold_used_rows.append(threshold_row)

    stage24 = pl.concat(rows, how="diagonal_relaxed").sort(["symbol", "split", "ts_event"])
    FINAL_WFA_BACKTEST.parent.mkdir(parents=True, exist_ok=True)
    stage24.write_parquet(FINAL_WFA_BACKTEST)
    expected_slots = len(getattr(config, "symbols", []) or []) * len(splits)
    write_lineage(
        FINAL_WFA_BACKTEST,
        run_id=run_id,
        profile=profile,
        source_stage="stage_23_frozen_feature_set",
        source_artifact_path=frozen_root / "manifest.json",
        frozen_feature_manifest_path=frozen_root / "manifest.json",
        selected_feature_count=len(features),
        expected_symbols=[str(s) for s in getattr(config, "symbols", []) or []],
        expected_splits=len(splits),
        expected_rows=expected_slots,
        actual_rows=stage24.height,
    )
    write_final_threshold_used(threshold_used_rows)

    stage25 = materialize_final_oos_predictions(
        run_id=run_id,
        profile=profile,
        source_path=FINAL_WFA_BACKTEST,
        out_path=FINAL_OOS_PREDICTIONS,
        target_col=target_col,
    )
    stage25 = validate_final_oos_predictions(
        path=FINAL_OOS_PREDICTIONS,
        target_col=target_col,
        expected_symbols=[str(s) for s in getattr(config, "symbols", []) or []],
        expected_splits=len(splits),
        source_path=FINAL_WFA_BACKTEST,
    )
    if stage25.get("status") != "PASS":
        raise RuntimeError(f"FINAL OOS FAIL: {stage25.get('reason')}")

    threshold_diagnostics = write_final_threshold_diagnostics(
        df=pl.read_parquet(FINAL_OOS_PREDICTIONS),
        config=config,
        run_id=run_id,
        profile=profile,
    )
    metrics_report = _write_stage26_metrics(config, run_id, profile, len(splits), expected_slots)
    gate_report = _write_stage27_gate(config, run_id, profile, metrics_report)
    diagnostics = write_final_gate_diagnostics(
        config=config,
        run_id=run_id,
        profile=profile,
        stage25_path=FINAL_OOS_PREDICTIONS,
        stage27_status=str(gate_report.get("strategy_acceptance_status") or gate_report.get("status") or ""),
    )
    experiment = write_final_experiment_reports(
        run_id=run_id,
        profile=profile,
        stage25_path=FINAL_OOS_PREDICTIONS,
        expected_rows=expected_slots,
        stage27_status=str(gate_report.get("strategy_acceptance_status") or gate_report.get("status") or ""),
    )
    trade_audit = write_final_trade_count_audit(
        run_id=run_id,
        profile=profile,
        config=config,
        stage25_path=FINAL_OOS_PREDICTIONS,
    )
    profile_comparison = update_final_threshold_profile_comparison(
        comparison=experiment,
        config=config,
        trade_audit=trade_audit,
    )
    frozen_set_comparison = write_frozen_set_comparison(current_run_id=run_id, frozen_root=frozen_root)
    return {
        "status": "PASS",
        "stage24_path": str(FINAL_WFA_BACKTEST),
        "stage25_path": str(FINAL_OOS_PREDICTIONS),
        "stage26_path": str(STAGE26_FINAL_METRICS),
        "stage27_path": str(STAGE27_FINAL_GATE),
        "expected_split_slots": expected_slots,
        "actual_split_slots": _actual_slot_count(FINAL_OOS_PREDICTIONS),
        "stage25_rows": stage25.get("row_count"),
        "stage26_source_checksum": file_sha256(FINAL_OOS_PREDICTIONS),
        "stage27_source_checksum": file_sha256(STAGE26_FINAL_METRICS),
        "final_gate_status": gate_report.get("strategy_acceptance_status") or gate_report.get("status"),
        "diagnostics": diagnostics,
        "threshold_diagnostics": threshold_diagnostics,
        "experiment": experiment,
        "trade_audit": trade_audit,
        "profile_comparison": profile_comparison,
        "frozen_set_comparison": frozen_set_comparison,
    }


def _run_symbol_split(
    *,
    symbol: str,
    split_idx: int,
    paths: list[Path],
    features: list[str],
    target_col: str,
    config: Any,
    train_start: Any,
    train_end: Any,
    test_start: Any,
    test_end: Any,
    run_id: str,
    profile: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    cols = _needed_columns(paths[0], features, target_col)
    df = pl.scan_parquet(paths).select(cols).collect().sort("ts_event")
    train, test = apply_walkforward_contract(
        df,
        train_start,
        train_end,
        test_start,
        test_end,
        target_horizon_bars=int(getattr(getattr(config, "target", object()), "target_15m_horizon", 0)),
        embargo_bars=int(getattr(getattr(config, "walkforward", object()), "embargo_bars", 0)),
        purge_target_overlap=bool(getattr(getattr(config, "walkforward", object()), "purge_target_overlap", True)),
        entry_lag_bars=int(getattr(getattr(config, "execution", object()), "entry_lag_bars", 1)),
    )
    train = train.drop_nulls([target_col])
    test = test.drop_nulls([target_col])
    if train.is_empty() or test.is_empty():
        raise RuntimeError(f"FINAL WFA FAIL: empty train/test symbol={symbol} split={split_idx}")

    context = {
        "config": config,
        "run_id": run_id,
        "symbol": symbol,
        "split_id": split_idx,
        "train_start": train_start,
        "train_end": train_end,
        "test_start": test_start,
        "test_end": test_end,
    }
    train_s, test_s, _ = fit_apply_train_scaler(train, test, features, context)
    beta, intercept = _fit_ridge(
        train_s,
        features,
        target_col,
        float(getattr(getattr(config, "walkforward", object()), "ridge_params", {"alpha": 1.0}).get("alpha", 1.0)),
    )
    train_pred = _predict(train_s, features, beta, intercept)
    threshold, _, _, _, train_abs_q = resolve_threshold_from_train(train_pred, config, calibration_source="train")
    pred = _predict(test_s, features, beta, intercept)
    result = _attach_execution(
        test_s,
        pred,
        target_col,
        config,
        feature_set_id=_feature_set_id(features),
        symbol=symbol,
        threshold=threshold,
    )
    result = result.with_columns(
        pl.lit(str(run_id)).alias("run_id"),
        pl.lit(str(profile)).alias("profile"),
        pl.lit(symbol).alias("symbol"),
        pl.lit(str(split_idx)).alias("split"),
        pl.col("ts_event").alias("timestamp"),
        pl.lit(str(train_start)).alias("train_start"),
        pl.lit(str(train_end)).alias("train_end"),
        pl.lit(str(test_start)).alias("test_start"),
        pl.lit(str(test_end)).alias("test_end"),
        pl.lit("full_research_frozen_features").alias("modeling_mode"),
    )
    threshold_row = build_final_threshold_used_row(
        run_id=run_id,
        profile=profile,
        symbol=symbol,
        split=split_idx,
        config=config,
        train_predictions=train_pred,
        train_abs_prediction_quantile=train_abs_q,
        threshold=threshold,
        test_result=result,
        calibration_source="train",
    )
    return result, threshold_row


def _write_stage26_metrics(config: Any, run_id: str, profile: str, expected_splits: int, expected_slots: int) -> dict[str, Any]:
    df = pl.read_parquet(FINAL_OOS_PREDICTIONS)
    metrics = compute_backtest_metrics(df)
    metrics["modeling_mode"] = "full_research"
    stress = run_stress_tests(df, config)
    report = {
        "stage": 26,
        "status": "PASS",
        "run_id": str(run_id),
        "profile": str(profile),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_stage": "stage_25_final_oos_predictions",
        "source_artifact_path": str(FINAL_OOS_PREDICTIONS),
        "source_artifact_checksum": file_sha256(FINAL_OOS_PREDICTIONS),
        "expected_split_slots": expected_slots,
        "actual_split_slots": _actual_slot_count(FINAL_OOS_PREDICTIONS),
        "expected_splits": expected_splits,
        "actual_rows": df.height,
        "metrics": metrics,
        **metrics,
        "stress": stress,
    }
    atomic_write_json(STAGE26_FINAL_METRICS, report)
    return report


def _write_stage27_gate(config: Any, run_id: str, profile: str, metrics_report: dict[str, Any]) -> dict[str, Any]:
    gate = run_acceptance_gate(
        metrics_report,
        metrics_report.get("stress"),
        context={"config": config, "modeling_mode": "full_research", "run_id": run_id, "profile": profile},
    )
    status = str(gate.get("status") or "")
    counts = {
        "ACCEPT": "1" if status == "ACCEPT" else "0",
        "REJECT": "1" if status == "REJECT" else "0",
        "WARN": "1" if status == "WARN" else "0",
        "MISSING": "0",
    }
    report = {
        **gate,
        "stage": 27,
        "run_id": str(run_id),
        "profile": str(profile),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_stage": "stage_26_final_metrics_diagnostics",
        "source_artifact_path": str(STAGE26_FINAL_METRICS),
        "source_artifact_checksum": file_sha256(STAGE26_FINAL_METRICS),
        **counts,
    }
    atomic_write_json(STAGE27_FINAL_GATE, report)
    return report


def _read_frozen_features(root: Path) -> list[str]:
    payload = json.loads((root / "feature_cols.json").read_text(encoding="utf-8"))
    features = [str(x) for x in (payload.get("feature_cols") or payload.get("selected_features") or [])]
    if not features:
        raise RuntimeError(f"FINAL WFA FAIL: empty frozen feature list: {root / 'feature_cols.json'}")
    return features


def _scoped_feature_files(root: Path, config: Any) -> list[Path]:
    symbols = {str(s) for s in getattr(config, "symbols", []) or []}
    start_year = getattr(config, "start_year", None)
    end_year = getattr(config, "end_year", None)
    files: list[Path] = []
    for path in sorted(root.glob("*/*.parquet")):
        if symbols and path.parent.name not in symbols:
            continue
        try:
            year = int(path.stem)
        except ValueError:
            continue
        if start_year is not None and year < int(start_year):
            continue
        if end_year is not None and year > int(end_year):
            continue
        files.append(path)
    return files


def _assert_columns_available(path: Path, features: list[str], target_col: str) -> None:
    schema = pl.scan_parquet(path).collect_schema()
    cols = set(schema.names())
    required = set(features) | {"ts_event", "open", "close", target_col}
    missing = sorted(required - cols)
    if missing:
        raise RuntimeError(f"FINAL WFA FAIL: selected/required columns missing from {path}: {missing}")


def _needed_columns(path: Path, features: list[str], target_col: str) -> list[str]:
    cols = set(pl.scan_parquet(path).collect_schema().names())
    base = ["ts_event", "open", "high", "low", "close", "volume", target_col, "label_target_scale_factor"]
    return [c for c in dict.fromkeys(base + features) if c in cols]


def _generate_splits(files: list[Path], config: Any) -> list[tuple]:
    bounds = _load_file_date_bounds(files)
    if not bounds:
        return []
    dates = sorted(d for b in bounds.values() for d in b)
    data_start = dates[0]
    data_end = dates[-1]
    wf = getattr(config, "walkforward", object())
    train_days = int(getattr(wf, "wf_train_days", 0) or 0)
    test_days = int(getattr(wf, "wf_test_days", 0) or 0)
    step_days = int(getattr(wf, "wf_step_days", 0) or 0)
    if train_days <= 0 or test_days <= 0 or step_days <= 0:
        years = sorted({int(p.stem) for p in files})
        return [(years[:-1], years[-1:])] if len(years) > 1 else [(years, years)]
    total_days = (data_end - data_start).days + 1
    window = train_days + test_days
    splits: list[tuple] = []
    cursor = 0
    while cursor + window <= total_days:
        train_start = data_start + timedelta(days=cursor)
        train_end = data_start + timedelta(days=cursor + train_days)
        test_start = train_end
        test_end = data_start + timedelta(days=cursor + window)
        train_years = [yr for yr, (lo, hi) in bounds.items() if hi >= train_start and lo < train_end]
        test_years = [yr for yr, (lo, hi) in bounds.items() if hi >= test_start and lo < test_end]
        if train_years and test_years:
            splits.append((sorted(train_years), sorted(test_years), train_start, train_end, test_start, test_end))
        cursor += step_days
    return splits


def _load_file_date_bounds(files: list[Path]) -> dict[int, tuple]:
    out: dict[int, tuple] = {}
    for p in files:
        try:
            year = int(p.stem)
            df = pl.scan_parquet(p).select(pl.col("ts_event").min().alias("min_ts"), pl.col("ts_event").max().alias("max_ts")).collect()
            lo = df["min_ts"][0]
            hi = df["max_ts"][0]
            if lo is not None and hi is not None:
                out[year] = (lo.date() if hasattr(lo, "date") else lo, hi.date() if hasattr(hi, "date") else hi)
        except Exception:
            continue
    return out


def _split_parts(split: tuple) -> tuple:
    if len(split) >= 6:
        return split[0], split[1], split[2], split[3], split[4], split[5]
    return split[0], split[1], None, None, None, None


def _actual_slot_count(path: str | Path) -> int:
    return pl.scan_parquet(path).select(["symbol", "split"]).unique().collect().height
