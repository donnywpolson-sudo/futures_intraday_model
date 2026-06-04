from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl


REPORT_CSV = Path("reports/validation/threshold_used.csv")
REPORT_JSON = Path("reports/validation/threshold_used.json")

FIELDS = [
    "run_id",
    "profile",
    "config_env",
    "created_at",
    "symbol",
    "split",
    "threshold_mode",
    "threshold_quantile",
    "train_prediction_nonnull",
    "train_abs_prediction_quantile",
    "long_threshold_used",
    "short_threshold_used",
    "test_prediction_nonnull",
    "test_active_bar_pct",
    "test_long_bars",
    "test_short_bars",
    "test_turnover",
]


def resolve_threshold_from_train(
    train_predictions: Any,
    config: Any,
    *,
    calibration_source: str = "train",
) -> tuple[float, str, float | None, int, float | None]:
    if calibration_source != "train":
        raise RuntimeError("THRESHOLD LEAKAGE FAIL: threshold calibration must use train predictions only")
    mode = str(getattr(config.execution, "threshold_mode", "fixed"))
    fixed = float(getattr(config.execution, "prediction_entry_threshold", 0.0))
    if mode == "fixed":
        arr = _finite_array(train_predictions)
        return fixed, mode, getattr(config.execution, "threshold_quantile", None), int(arr.size), None
    if mode != "prediction_abs_quantile":
        raise ValueError(f"unsupported execution.threshold_mode={mode!r}")
    q = getattr(config.execution, "threshold_quantile", None)
    if q is None or not (0.0 < float(q) < 1.0):
        raise ValueError(f"invalid execution.threshold_quantile={q!r}")
    arr = np.abs(_finite_array(train_predictions))
    if arr.size == 0:
        raise RuntimeError("THRESHOLD CALIBRATION FAIL: no finite train predictions")
    threshold = float(np.quantile(arr, float(q)))
    return threshold, mode, float(q), int(arr.size), threshold


def write_threshold_used(
    *,
    symbol: str,
    split: str | int,
    config: Any,
    train_predictions: Any,
    test_result: pl.DataFrame,
    threshold: float,
    train_abs_prediction_quantile: float | None,
) -> dict[str, Any]:
    mode = str(getattr(config.execution, "threshold_mode", "fixed"))
    q = getattr(config.execution, "threshold_quantile", None)
    test_pred = test_result["prediction"].cast(pl.Float64).drop_nulls() if "prediction" in test_result.columns else pl.Series([], dtype=pl.Float64)
    pos = test_result["position_after"].cast(pl.Float64) if "position_after" in test_result.columns else (
        test_result["position"].cast(pl.Float64) if "position" in test_result.columns else pl.Series([0.0] * test_result.height)
    )
    delta = test_result["position_delta"].abs().cast(pl.Float64) if "position_delta" in test_result.columns else pl.Series([0.0] * test_result.height)
    row = {
        **_metadata(),
        "symbol": symbol,
        "split": split,
        "threshold_mode": mode,
        "threshold_quantile": "" if q is None else float(q),
        "train_prediction_nonnull": int(_finite_array(train_predictions).size),
        "train_abs_prediction_quantile": "" if train_abs_prediction_quantile is None else float(train_abs_prediction_quantile),
        "long_threshold_used": float(threshold),
        "short_threshold_used": -float(threshold),
        "test_prediction_nonnull": int(test_pred.len()),
        "test_active_bar_pct": 0.0 if test_result.height == 0 else float((pos != 0).sum() or 0) / test_result.height,
        "test_long_bars": int((pos > 0).sum() or 0) if len(pos) else 0,
        "test_short_bars": int((pos < 0).sum() or 0) if len(pos) else 0,
        "test_turnover": float(delta.sum() or 0.0) if len(delta) else 0.0,
    }
    _append(row)
    return row


def _finite_array(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return arr[np.isfinite(arr)]


def _append(row: dict[str, Any]) -> None:
    row = {**_metadata(), **row}
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    run_id = str(row.get("run_id", "manual"))
    if REPORT_JSON.exists():
        try:
            raw = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
            rows = raw if isinstance(raw, list) else []
        except Exception:
            rows = []
    rows = [r for r in rows if str(r.get("run_id", "manual")) == run_id]
    key = (str(row.get("run_id", "")), str(row.get("symbol", "")), str(row.get("split", "")))
    rows = [
        r for r in rows
        if (str(r.get("run_id", "")), str(r.get("symbol", "")), str(r.get("split", ""))) != key
    ]
    rows.append({k: row.get(k, "") for k in FIELDS})
    with REPORT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    REPORT_JSON.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")


def threshold_used_row_count(run_id: str, symbol: str, split: str | int, path: Path = REPORT_JSON) -> int:
    rows = _read_json_list(path)
    return sum(
        1
        for r in rows
        if str(r.get("run_id")) == str(run_id)
        and str(r.get("symbol")) == str(symbol)
        and str(r.get("split")) == str(split)
    )


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _metadata() -> dict[str, str]:
    config_env = os.environ.get("CONFIG_ENV") or os.environ.get("QUANT_ENV") or ""
    return {
        "run_id": os.environ.get("PARENT_RUN_ID") or os.environ.get("QUANT_RUN_ID") or "manual",
        "profile": os.environ.get("QUANT_RUN_PROFILE") or config_env,
        "config_env": config_env,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
