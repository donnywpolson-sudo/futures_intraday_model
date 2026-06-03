from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.analytics.aggregate import compute_backtest_metrics, write_metrics_report
from pipeline.audit.execution_trace import build_execution_trace, validate_execution_trace, write_execution_trace_outputs
from pipeline.audit.leakage import run_leakage_audit
from pipeline.audit.run_manifest import write_run_manifest
from pipeline.common.config import RootConfig, config as flat_config, load_config
from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.gates.acceptance import run_acceptance_gate
from pipeline.gates.deployment import run_deployment_readiness
from pipeline.stress.stress_tests import run_stress_tests


EXCLUDE_COLS = {
    "ts_event", "date", "session", "session_id", "open", "high", "low", "close", "volume",
    "prediction_time", "execution_time", "pnl", "gross_pnl", "net_pnl", "fees", "slippage",
    "position_before", "position_after", "position_delta", "raw_signal", "prediction_prob",
}

MINIMAL_MODELING_WARNING = "minimal_compatible modeling validates pipeline wiring only; it is not strategy evidence"


def _load_cfg() -> RootConfig:
    cfg = load_config(os.environ.get("CONFIG_ENV") or os.environ.get("QUANT_ENV"))
    if cfg is None:
        # load_config is idempotent and may return None after first call in tests.
        return RootConfig()
    return cfg


def _read_data(pattern: str, start: str | None = None, end: str | None = None) -> pl.DataFrame:
    paths = sorted(Path().glob(pattern)) if any(ch in pattern for ch in "*?[]") else [Path(pattern)]
    if not paths:
        raise FileNotFoundError(f"no data files matched: {pattern}")
    frames = [pl.read_parquet(p) for p in paths]
    df = pl.concat(frames, how="diagonal") if len(frames) > 1 else frames[0]
    if "ts_event" in df.columns:
        if start:
            df = df.filter(pl.col("ts_event") >= pl.lit(_parse_like_ts(start, df["ts_event"].dtype)).cast(df["ts_event"].dtype))
        if end:
            df = df.filter(pl.col("ts_event") < pl.lit(_parse_like_ts(end, df["ts_event"].dtype)).cast(df["ts_event"].dtype))
    return df.sort("ts_event") if "ts_event" in df.columns else df


def _parse_like_ts(value: str, dtype: pl.DataType) -> Any:
    if dtype in (pl.Int64, pl.Int32, pl.UInt64, pl.UInt32):
        return int(float(value))
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if getattr(dtype, "time_zone", None):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=None)
    except Exception:
        return value


def _symbol_from_path(path: str) -> str:
    p = Path(path)
    return p.parent.name if p.parent.name else p.stem.split("_")[0]


def _ensure_target(df: pl.DataFrame, target_col: str) -> pl.DataFrame:
    if target_col in df.columns:
        return df
    price = "open" if "open" in df.columns else "close"
    if price not in df.columns:
        raise ValueError(f"cannot derive {target_col}: missing open/close")
    return df.with_columns(((pl.col(price).shift(-16) / pl.col(price).shift(-1)).log()).alias(target_col))


def _enforce_safe_label_end(df: pl.DataFrame, end: str | None, cfg: RootConfig) -> pl.DataFrame:
    if not end or "ts_event" not in df.columns:
        return df
    dtype = df["ts_event"].dtype
    horizon_min = int(cfg.target.target_15m_horizon) * 5
    if dtype in (pl.Int64, pl.Int32, pl.UInt64, pl.UInt32):
        cutoff = int(float(end)) - horizon_min
        return df.filter(pl.col("ts_event") < cutoff)
    try:
        from datetime import timedelta

        cutoff = _parse_like_ts(end, dtype) - timedelta(minutes=horizon_min)
        return df.filter(pl.col("ts_event") < pl.lit(cutoff).cast(dtype))
    except Exception:
        return df.head(max(df.height - horizon_min, 0))


def _add_basic_features(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    if "close" in df.columns:
        exprs.append(pl.col("close").pct_change().fill_null(0).alias("ret_1"))
    if "volume" in df.columns:
        exprs.append(pl.col("volume").cast(pl.Float64).pct_change().fill_null(0).alias("volume_chg"))
    return df.with_columns(exprs) if exprs else df


def _feature_cols(df: pl.DataFrame, target_col: str, cfg: RootConfig) -> list[str]:
    forbidden = list(cfg.leakage_audit.forbidden_feature_prefixes) + list(cfg.leakage_audit.forbidden_model_metadata_prefixes)
    cols = []
    for c, dtype in zip(df.columns, df.dtypes):
        if c == target_col or c in EXCLUDE_COLS:
            continue
        if any(c.startswith(p) for p in forbidden):
            continue
        if dtype.is_numeric():
            cols.append(c)
    return cols


def _forbidden_input_columns(df: pl.DataFrame, target_col: str, cfg: RootConfig) -> list[str]:
    bad = []
    for c in df.columns:
        if c == target_col:
            continue
        if c.startswith("future_") or c.startswith("label_") or c.startswith("target_"):
            bad.append(c)
    return bad


def _window_name(args: argparse.Namespace) -> str:
    raw = "_".join(str(x or "none") for x in [getattr(args, "start", None), getattr(args, "end", None)])
    return "".join(ch if ch.isalnum() else "-" for ch in raw)[:80]


def cmd_discover(args: argparse.Namespace) -> None:
    cfg = _load_cfg()
    df = _add_basic_features(_read_data(args.data, args.start, args.end))
    target_col = getattr(flat_config, "DISCOVERY_TARGET", cfg.walkforward.discovery_target)
    df = _ensure_target(df, target_col)
    df = _enforce_safe_label_end(df, args.end, cfg)
    features = _feature_cols(df, target_col, cfg)
    payload = {
        "status": "PASS",
        "target_col": target_col,
        "feature_cols": features,
        "selected_features": features,
        "rows": df.height,
        "start": args.start,
        "end": args.end,
    }
    atomic_write_json(args.out, payload)
    print(f"[CLI] discovery manifest: {args.out} features={len(features)} rows={df.height}")


def _load_manifest_features(path: str | None) -> list[str]:
    if not path or not Path(path).exists():
        return []
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return list(raw.get("selected_features") or raw.get("feature_cols") or [])
    except Exception:
        return []


def _run_minimal_compatible_modeling(df: pl.DataFrame, features: list[str], target_col: str, cfg: RootConfig) -> pl.DataFrame:
    if not features:
        raise ValueError("no model features available after safe feature selection")
    score_expr = sum([pl.col(c).fill_null(0).cast(pl.Float64) for c in features]) / float(len(features))
    df = df.with_columns(score_expr.tanh().alias("_score"))
    df = df.with_columns(
        (0.5 + 0.25 * pl.col("_score")).clip(0.0, 1.0).alias("prediction_prob"),
        pl.when(pl.col("_score") > 0).then(1).when(pl.col("_score") < 0).then(-1).otherwise(0).alias("raw_signal"),
    )
    if "ts_event" in df.columns:
        if df["ts_event"].dtype in (pl.Int64, pl.Int32, pl.UInt64, pl.UInt32):
            exec_time = pl.col("ts_event") + int(cfg.execution.entry_lag_bars)
        else:
            exec_time = pl.col("ts_event") + pl.duration(minutes=int(cfg.execution.entry_lag_bars))
        df = df.with_columns(pl.col("ts_event").alias("prediction_time"), exec_time.alias("execution_time"))
    fill = "open" if "open" in df.columns else "close"
    if fill not in df.columns:
        raise ValueError("missing fill price column: open/close")
    df = df.with_columns(
        pl.col("raw_signal").shift(1).fill_null(0).alias("position_before"),
        pl.col("raw_signal").clip(-cfg.execution.max_contracts, cfg.execution.max_contracts).alias("position_after"),
        pl.col(fill).alias("assumed_fill_price"),
    )
    df = df.with_columns((pl.col("position_after") - pl.col("position_before")).alias("position_delta"))
    ret = pl.col(target_col).fill_null(0).cast(pl.Float64)
    costs = pl.col("position_delta").abs() * (
        float(cfg.execution.commission_per_contract)
        + float(cfg.execution.exchange_fees_per_contract)
        + float(cfg.execution.slippage_ticks)
        + float(cfg.execution.spread_ticks) * 0.5
    )
    df = df.with_columns(
        ret.alias("ret_exec"),
        (pl.col("position_after") * ret).alias("gross_pnl"),
        costs.alias("fees"),
        (pl.col("position_delta").abs() * float(cfg.execution.slippage_ticks)).alias("slippage"),
    )
    df = df.with_columns((pl.col("gross_pnl") - pl.col("fees") - pl.col("slippage")).alias("pnl"))
    df = df.with_columns(
        pl.col("pnl").alias("net_pnl"),
        pl.col("pnl").cum_sum().alias("equity_curve"),
    )
    df = df.with_columns((pl.col("equity_curve") - pl.col("equity_curve").cum_max()).alias("drawdown_pct"))
    return df.drop_nulls([target_col, "prediction_prob", "pnl"])


def _run_full_research_modeling(df: pl.DataFrame, features: list[str], target_col: str, cfg: RootConfig, context: dict[str, Any]) -> pl.DataFrame:
    required = [
        "pipeline.ingest.ingest",
        "pipeline.features.engine",
        "pipeline.features.discovery",
        "pipeline.walkforward.walkforward",
    ]
    missing = [mod for mod in required if importlib.util.find_spec(mod) is None]
    if missing:
        raise RuntimeError(
            "FULL_RESEARCH MODELING FAIL: required legacy modules are missing: "
            + ", ".join(missing)
            + ". Restore these modules or set pipeline.modeling_mode='minimal_compatible'."
        )
    raise RuntimeError("FULL_RESEARCH MODELING FAIL: full research adapter is not wired yet.")


def run_modeling_pipeline(
    df: pl.DataFrame,
    feature_cols: list[str],
    target_col: str,
    train_start: str | None,
    train_end: str | None,
    test_start: str | None,
    test_end: str | None,
    context: dict[str, Any],
) -> pl.DataFrame:
    cfg: RootConfig = context["config"]
    mode = getattr(cfg.pipeline, "modeling_mode", "minimal_compatible")
    if mode == "minimal_compatible":
        return _run_minimal_compatible_modeling(df, feature_cols, target_col, cfg)
    if mode == "full_research":
        return _run_full_research_modeling(df, feature_cols, target_col, cfg, context)
    raise ValueError(f"unsupported pipeline.modeling_mode={mode!r}; expected minimal_compatible or full_research")


def _json_status(path: Path) -> str:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status", "UNKNOWN")
    except Exception:
        return "MISSING"


def cmd_run(args: argparse.Namespace, hmm: bool = False) -> None:
    cfg = _load_cfg()
    command = "run-hmm" if hmm else "run"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbol = _symbol_from_path(args.data)
    window = _window_name(args)
    profile = getattr(flat_config, "ACTIVE_PROFILE", cfg.__class__.__name__)
    modeling_mode = getattr(cfg.pipeline, "modeling_mode", "minimal_compatible")
    if modeling_mode == "minimal_compatible":
        print(f"[CLI] WARNING modeling_mode=minimal_compatible: {MINIMAL_MODELING_WARNING}")
    df = _add_basic_features(_read_data(args.data, args.start, args.end))
    target_col = getattr(flat_config, "WALKFORWARD_TARGET", cfg.walkforward.walkforward_target)
    df = _ensure_target(df, target_col)
    df = _enforce_safe_label_end(df, args.end, cfg)
    bad = _forbidden_input_columns(df, target_col, cfg)
    if bad:
        raise SystemExit(f"LEAKAGE FAIL: forbidden input columns present before modeling: {bad}")
    manifest_features = _load_manifest_features(args.manifest)
    safe_features = _feature_cols(df, target_col, cfg)
    features = [c for c in manifest_features if c in safe_features] or safe_features
    leakage_path = Path(cfg.leakage_audit.report_dir) / f"{profile}_{symbol}_{command}_{window}.json"
    leakage = run_leakage_audit(df, features, target_col, context={"out": str(leakage_path), "symbol": symbol, "command": command})
    if cfg.leakage_audit.fail_on_error and leakage["status"] == "FAIL":
        raise SystemExit(f"LEAKAGE FAIL: {leakage_path}")
    result = run_modeling_pipeline(
        df,
        features,
        target_col,
        args.train_start,
        args.train_end,
        args.start,
        args.end,
        {"config": cfg, "symbol": symbol, "command": command},
    )
    result_path = out_dir / ("backtest_results_hmm.parquet" if hmm else "backtest_results.parquet")
    result.write_parquet(result_path)
    result.select([c for c in ["ts_event", "prediction_time", "prediction_prob", "raw_signal", "pnl"] if c in result.columns]).write_parquet(out_dir / "oos_predictions.parquet")
    metrics = compute_backtest_metrics(result)
    metrics["modeling_mode"] = modeling_mode
    if modeling_mode == "minimal_compatible":
        metrics["warnings"] = [MINIMAL_MODELING_WARNING]
    metrics_path = Path("reports/metrics") / f"{profile}_{symbol}_{command}_{window}_metrics_report.json"
    atomic_write_json(metrics_path, metrics)
    write_csv_rows(metrics_path.with_suffix(".csv"), [metrics])
    trace = build_execution_trace(result, max_rows=cfg.execution.execution_trace_rows)
    exec_report = validate_execution_trace(trace, cfg)
    write_execution_trace_outputs(trace, exec_report, out_dir)
    if cfg.acceptance_gate.fail_on_execution_trace_error and exec_report["status"] == "FAIL":
        raise SystemExit(f"EXECUTION TRACE FAIL: {out_dir / 'execution_trace_report.json'}")
    stress = None
    stress_path = None
    if cfg.stress_tests.enabled:
        stress_prefix = Path(cfg.stress_tests.report_dir) / f"{profile}_{symbol}_{command}_{window}_stress_report"
        stress = run_stress_tests(result, cfg, stress_prefix)
        stress_path = stress_prefix.with_suffix(".json")
    acceptance_path = Path(cfg.acceptance_gate.report_dir) / f"{profile}_{symbol}_{command}_{window}_acceptance_gate.json"
    acceptance = run_acceptance_gate(metrics, stress, leakage, exec_report, context={"config": cfg, "out": str(acceptance_path), "symbol": symbol, "command": command, "modeling_mode": modeling_mode})
    if acceptance["status"] == "REJECT":
        failed = [g["name"] for g in acceptance.get("gates", []) if g.get("status") == "FAIL"]
        print(f"[CLI] ACCEPTANCE REJECT: {acceptance_path} failed_gates={','.join(failed)}")
        if os.environ.get("QUANT_ACCEPTANCE_GATE_REQUIRED") == "1" or cfg.acceptance_gate.required:
            raise SystemExit(f"ACCEPTANCE GATE REJECT: {acceptance_path} failed_gates={','.join(failed)}")
    print(f"[CLI] Running {'HMM-aware ' if hmm else ''}walkforward")
    print(f"[CLI] {'HMM ' if hmm else ''}walkforward result: {result.height:,} rows")
    print(f"[CLI] wrote {result_path}")
    write_run_manifest(
        run_id=Path(out_dir).name,
        config=cfg,
        files=[Path(args.data)],
        audit_paths={
            "leakage": str(leakage_path),
            "execution_trace": str(out_dir / "execution_trace_report.json"),
            "metrics": str(metrics_path),
            "stress": str(stress_path) if stress_path else "",
            "acceptance": str(acceptance_path),
            "output": str(result_path),
            "oos_predictions": str(out_dir / "oos_predictions.parquet"),
            "cli_command": command,
        },
        splits=[
            {
                "symbol": symbol,
                "train_start": args.train_start,
                "train_end": args.train_end,
                "test_start": args.start,
                "test_end": args.end,
                "backtest_results": str(result_path),
                "oos_predictions": str(out_dir / "oos_predictions.parquet"),
                "leakage_report": str(leakage_path),
                "leakage_status": leakage.get("status"),
                "execution_trace_report": str(out_dir / "execution_trace_report.json"),
                "execution_trace_status": exec_report.get("status"),
                "metrics_report": str(metrics_path),
                "metrics_status": "PASS",
                "stress_report": str(stress_path) if stress_path else "",
                "stress_status": stress.get("status") if stress else "MISSING",
                "acceptance_report": str(acceptance_path),
                "acceptance_status": acceptance.get("status"),
            }
        ],
    )


def cmd_aggregate(args: argparse.Namespace) -> None:
    cfg = _load_cfg()
    root = Path(args.artifacts)
    paths = sorted(root.rglob("backtest_results*.parquet"))
    if not paths:
        raise SystemExit(f"AGGREGATE FAIL: no backtest_results parquet under {root}")
    df = pl.concat([pl.read_parquet(p) for p in paths], how="diagonal")
    metrics = write_metrics_report(df, getattr(flat_config, "ACTIVE_PROFILE", "profile"))
    run_deployment_readiness(cfg)
    print(json.dumps({"status": "PASS", "files": len(paths), "metrics": metrics}, default=str))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--data", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--start")
    d.add_argument("--end")
    r = sub.add_parser("run")
    r.add_argument("--data", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--train-start")
    r.add_argument("--train-end")
    r.add_argument("--start")
    r.add_argument("--end")
    rh = sub.add_parser("run-hmm")
    rh.add_argument("--data", required=True)
    rh.add_argument("--manifest", required=True)
    rh.add_argument("--out", required=True)
    rh.add_argument("--train-start")
    rh.add_argument("--train-end")
    rh.add_argument("--start")
    rh.add_argument("--end")
    a = sub.add_parser("aggregate")
    a.add_argument("--artifacts", default="output")
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "discover":
        cmd_discover(args)
    elif args.cmd == "run":
        cmd_run(args, hmm=False)
    elif args.cmd == "run-hmm":
        cmd_run(args, hmm=True)
    elif args.cmd == "aggregate":
        cmd_aggregate(args)


if __name__ == "__main__":
    main()
