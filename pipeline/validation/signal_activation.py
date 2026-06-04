from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


REPORT_CSV = Path("reports/validation/signal_activation_debug.csv")
REPORT_JSON = Path("reports/validation/signal_activation_debug.json")

FIELDS = [
    "run_id",
    "profile",
    "config_env",
    "created_at",
    "symbol",
    "split",
    "prediction_col",
    "prediction_count",
    "prediction_nonnull",
    "prediction_min",
    "prediction_max",
    "prediction_mean",
    "prediction_std",
    "prediction_abs_max",
    "signal_threshold_long",
    "signal_threshold_short",
    "long_bars",
    "short_bars",
    "flat_bars",
    "active_bar_pct",
    "position_turnover",
    "position_min",
    "position_max",
    "position_unique_values",
    "risk_gate_applied",
    "acceptance_gate_applied",
    "reason_if_flat",
]


def build_signal_activation_row(
    df: pl.DataFrame,
    *,
    symbol: str,
    split: str | int,
    config: Any | None = None,
) -> dict[str, Any]:
    pred_col = "prediction" if "prediction" in df.columns else ("prediction_prob" if "prediction_prob" in df.columns else "")
    threshold = _threshold(df, config)
    long_th = threshold
    short_th = -threshold
    n = int(df.height)
    pred = df[pred_col].cast(pl.Float64) if pred_col else pl.Series([], dtype=pl.Float64)
    pred_nonnull = int(pred.drop_nulls().len()) if pred_col else 0

    if "raw_signal" in df.columns:
        sig = df["raw_signal"].cast(pl.Float64)
        long_bars = int((sig > 0).sum() or 0)
        short_bars = int((sig < 0).sum() or 0)
    else:
        long_bars = 0
        short_bars = 0

    pos_col = "position_after" if "position_after" in df.columns else ("position" if "position" in df.columns else "")
    pos = df[pos_col].cast(pl.Float64) if pos_col else pl.Series([0.0] * n)
    active = int((pos != 0).sum() or 0) if len(pos) else 0
    delta = df["position_delta"].abs().cast(pl.Float64) if "position_delta" in df.columns else pl.Series([0.0] * n)
    risk_gate = _bool_col_any(df, "risk_gate_applied") or _bool_col_any(df, "risk_gate_forced_flat")
    acceptance_gate = _bool_col_any(df, "acceptance_gate_applied") or _bool_col_any(df, "acceptance_gate_forced_flat")
    row = {
        "symbol": symbol,
        "split": split,
        "prediction_col": pred_col,
        "prediction_count": n if pred_col else 0,
        "prediction_nonnull": pred_nonnull,
        "prediction_min": _float(pred.min()) if pred_nonnull else "",
        "prediction_max": _float(pred.max()) if pred_nonnull else "",
        "prediction_mean": _float(pred.mean()) if pred_nonnull else "",
        "prediction_std": _float(pred.std()) if pred_nonnull else "",
        "prediction_abs_max": _float(pred.abs().max()) if pred_nonnull else "",
        "signal_threshold_long": long_th,
        "signal_threshold_short": short_th,
        "long_bars": long_bars,
        "short_bars": short_bars,
        "flat_bars": n - active,
        "active_bar_pct": 0.0 if n == 0 else active / n,
        "position_turnover": _float(delta.sum()) if len(delta) else 0.0,
        "position_min": _float(pos.min()) if len(pos) else "",
        "position_max": _float(pos.max()) if len(pos) else "",
        "position_unique_values": "|".join(str(x) for x in sorted(pos.drop_nulls().unique().to_list())) if len(pos) else "",
        "risk_gate_applied": bool(risk_gate),
        "acceptance_gate_applied": bool(acceptance_gate),
        "reason_if_flat": "",
    }
    row["reason_if_flat"] = classify_flat_reason(df, row)
    return row


def classify_flat_reason(df: pl.DataFrame, row: dict[str, Any]) -> str:
    if float(row.get("active_bar_pct") or 0.0) > 0.0:
        return ""
    pred_nonnull = int(row.get("prediction_nonnull") or 0)
    if not row.get("prediction_col") or pred_nonnull == 0:
        return "predictions all null"
    if "raw_signal" not in df.columns:
        return "signal column missing"
    if row.get("risk_gate_applied"):
        return "risk gate forced flat"
    if row.get("acceptance_gate_applied"):
        return "acceptance gate forced flat"
    pred_std = row.get("prediction_std")
    if pred_std == "" or abs(float(pred_std or 0.0)) < 1e-15:
        return "predictions constant"
    threshold = row.get("signal_threshold_long")
    if threshold == "" or threshold is None:
        return "threshold missing/invalid"
    if float(row.get("prediction_abs_max") or 0.0) <= abs(float(threshold)):
        return "predictions too small for threshold"
    if (int(row.get("long_bars") or 0) + int(row.get("short_bars") or 0)) > 0:
        return "position column overwritten to zero"
    return "threshold missing/invalid"


def write_signal_activation_row(row: dict[str, Any]) -> None:
    row = {**_metadata(), **row}
    _upsert_csv_json(REPORT_CSV, REPORT_JSON, FIELDS, row, key_fields=["run_id", "symbol", "split"])


def write_signal_activation_debug(df: pl.DataFrame, *, symbol: str, split: str | int, config: Any | None = None) -> dict[str, Any]:
    row = build_signal_activation_row(df, symbol=symbol, split=split, config=config)
    write_signal_activation_row(row)
    return row


def _metadata() -> dict[str, str]:
    config_env = os.environ.get("CONFIG_ENV") or os.environ.get("QUANT_ENV") or ""
    return {
        "run_id": os.environ.get("PARENT_RUN_ID") or os.environ.get("QUANT_RUN_ID") or "manual",
        "profile": os.environ.get("QUANT_RUN_PROFILE") or config_env,
        "config_env": config_env,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _upsert_csv_json(csv_path: Path, json_path: Path, fields: list[str], row: dict[str, Any], key_fields: list[str]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    run_id = str(row.get("run_id", "manual"))
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else []
        except Exception:
            rows = []
    rows = [r for r in rows if str(r.get("run_id", "manual")) == run_id]
    key = tuple(str(row.get(k, "")) for k in key_fields)
    rows = [r for r in rows if tuple(str(r.get(k, "")) for k in key_fields) != key]
    rows.append({k: row.get(k, "") for k in fields})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")


def _threshold(df: pl.DataFrame, config: Any | None) -> float | str:
    if "signal_entry_threshold" in df.columns:
        vals = df["signal_entry_threshold"].drop_nulls()
        if vals.len():
            return _float(vals[0])
    if config is not None:
        try:
            return float(config.execution.prediction_entry_threshold)
        except Exception:
            return ""
    return ""


def _bool_col_any(df: pl.DataFrame, col: str) -> bool:
    return bool(col in df.columns and df[col].fill_null(False).cast(pl.Boolean).any())


def _float(value: Any) -> float | str:
    try:
        if value is None:
            return ""
        return float(value)
    except Exception:
        return ""
