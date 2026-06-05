from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.validation.diagnostic_io import read_json_rows, write_csv_json


RAW_FORENSICS_CSV = Path("reports/validation/es_split_22_raw_forensics.csv")
RAW_FORENSICS_JSON = Path("reports/validation/es_split_22_raw_forensics.json")
TOP_BAR_TRACE_CSV = Path("reports/validation/es_split_22_top_bar_trace.csv")
TOP_BAR_TRACE_JSON = Path("reports/validation/es_split_22_top_bar_trace.json")
CALENDAR_ANOMALIES_CSV = Path("reports/validation/es_split_22_calendar_anomalies.csv")
CALENDAR_ANOMALIES_JSON = Path("reports/validation/es_split_22_calendar_anomalies.json")
ROBUST_ALPHA_CSV = Path("reports/validation/robust_alpha_evidence.csv")
ROBUST_ALPHA_JSON = Path("reports/validation/robust_alpha_evidence.json")

DEFAULT_STAGE24_PATH = Path("reports/validation/stage_24_final_wfa_backtest_results.parquet")
DEFAULT_BREAKDOWN_PATH = Path("reports/validation/final_gate_breakdown.json")
DEFAULT_OUTLIERS_PATH = Path("reports/validation/final_threshold_outliers.json")
DEFAULT_FEATURE_COLS_PATH = Path("data/frozen_features/phase5_v1/feature_cols.json")

SOURCE_STAGES = {
    "raw": Path("data/raw"),
    "validated": Path("data/validated"),
    "session_normalized": Path("data/session_normalized"),
    "causally_gated": Path("data/causally_gated_normalized"),
    "labeled": Path("data/labeled"),
    "feature_matrix": Path("data/feature_matrices/expanded"),
}

RAW_FORENSICS_FIELDS = [
    "run_id", "profile", "symbol", "split", "timestamp", "source_stage", "value_available",
    "open", "high", "low", "close", "volume", "target_15m_ret", "prediction", "position",
    "pnl_increment", "session_id", "session_date", "session_boundary_flag",
    "missing_bar_gap_flag", "extreme_return_flag", "extreme_volume_flag",
]
TOP_BAR_FIELDS = [
    "run_id", "profile", "symbol", "split", "pnl_rank", "timestamp", "raw_ohlcv",
    "normalized_ohlcv", "labeled_target", "frozen_feature_values", "prediction",
    "signal", "position", "cost", "net_pnl_contribution",
]
CALENDAR_FIELDS = [
    "run_id", "profile", "symbol", "split", "timestamp", "session_id", "session_date",
    "anomaly_type", "gap_minutes", "volume", "surrounding_median_volume", "reason",
]
ROBUST_FIELDS = [
    "run_id", "profile", "full_net_pnl", "net_pnl_excluding_es_split_22",
    "net_pnl_excluding_threshold_outliers", "net_pnl_excluding_top_1_pnl_bars",
    "net_pnl_excluding_top_5_pnl_bars", "net_pnl_excluding_top_10_pnl_bars",
    "ACCEPT", "REJECT", "accept_excluding_es_split_22", "reject_excluding_es_split_22",
    "accept_excluding_threshold_outliers", "reject_excluding_threshold_outliers", "conclusion",
]


def write_es_split_22_trace_diagnostics(
    *,
    run_id: str = "run_83ea5c92",
    profile: str = "tier_1_final_threshold_p999_experiment",
    symbol: str = "ES",
    split: str | int = "22",
    stage24_path: str | Path = DEFAULT_STAGE24_PATH,
    breakdown_path: str | Path = DEFAULT_BREAKDOWN_PATH,
    threshold_outliers_path: str | Path = DEFAULT_OUTLIERS_PATH,
    feature_cols_path: str | Path = DEFAULT_FEATURE_COLS_PATH,
    source_roots: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    split = str(split)
    final_df = _final_split_df(stage24_path, run_id, symbol, split)
    if final_df.is_empty():
        raise RuntimeError(f"ES SPLIT TRACE FAIL: no final rows for run_id={run_id} symbol={symbol} split={split}")

    top = _top_positive_bars(final_df, 10).sort("timestamp")
    flags = _row_flags(final_df)
    sources = {k: Path(v) for k, v in (source_roots or SOURCE_STAGES).items()}
    stage_maps = _source_stage_maps(sources, symbol, top["timestamp"].to_list())
    feature_cols = _feature_cols(feature_cols_path)

    raw_rows = _raw_forensic_rows(run_id, profile, symbol, split, top, stage_maps, flags)
    top_rows = _top_bar_rows(run_id, profile, symbol, split, top, stage_maps, feature_cols)
    calendar_rows = _calendar_anomaly_rows(run_id, profile, symbol, split, final_df)
    robust_rows = [
        _robust_alpha_row(
            run_id,
            profile,
            stage24_path=stage24_path,
            breakdown_path=breakdown_path,
            threshold_outliers_path=threshold_outliers_path,
        )
    ]

    write_csv_json(raw_rows, csv_path=RAW_FORENSICS_CSV, json_path=RAW_FORENSICS_JSON, fields=RAW_FORENSICS_FIELDS)
    write_csv_json(top_rows, csv_path=TOP_BAR_TRACE_CSV, json_path=TOP_BAR_TRACE_JSON, fields=TOP_BAR_FIELDS)
    write_csv_json(calendar_rows, csv_path=CALENDAR_ANOMALIES_CSV, json_path=CALENDAR_ANOMALIES_JSON, fields=CALENDAR_FIELDS)
    write_csv_json(robust_rows, csv_path=ROBUST_ALPHA_CSV, json_path=ROBUST_ALPHA_JSON, fields=ROBUST_FIELDS)

    return {
        "raw_forensic_rows": len(raw_rows),
        "top_bar_rows": len(top_rows),
        "calendar_anomaly_rows": len(calendar_rows),
        "robust_alpha": robust_rows[0],
    }


def _final_split_df(stage24_path: str | Path, run_id: str, symbol: str, split: str) -> pl.DataFrame:
    return (
        pl.scan_parquet(stage24_path)
        .filter(
            (pl.col("run_id") == run_id)
            & (pl.col("symbol") == symbol)
            & (pl.col("split").cast(pl.Utf8) == str(split))
        )
        .collect()
        .sort("timestamp")
    )


def _top_positive_bars(df: pl.DataFrame, n: int) -> pl.DataFrame:
    work = df.with_row_index("_row_order")
    return (
        work.sort("net_pnl", descending=True)
        .head(n)
        .with_row_index("pnl_rank", offset=1)
        .sort("timestamp")
    )


def _source_stage_maps(roots: dict[str, Path], symbol: str, timestamps: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    years = sorted({_year(ts) for ts in timestamps if _year(ts)})
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for stage, root in roots.items():
        frames = []
        for year in years:
            path = root / symbol / f"{year}.parquet"
            if path.exists():
                frames.append(pl.scan_parquet(path).collect())
        if not frames:
            out[stage] = {}
            continue
        df = pl.concat(frames, how="diagonal_relaxed")
        ts_col = "timestamp" if "timestamp" in df.columns else "ts_event"
        wanted = {_ts_key(ts) for ts in timestamps}
        out[stage] = {
            _ts_key(r.get(ts_col)): r
            for r in df.filter(pl.col(ts_col).map_elements(lambda x: _ts_key(x) in wanted, return_dtype=pl.Boolean)).iter_rows(named=True)
        }
    return out


def _raw_forensic_rows(
    run_id: str,
    profile: str,
    symbol: str,
    split: str,
    top: pl.DataFrame,
    stage_maps: dict[str, dict[str, dict[str, Any]]],
    flags: dict[str, dict[str, bool]],
) -> list[dict[str, Any]]:
    rows = []
    final_map = {_ts_key(r["timestamp"]): r for r in top.iter_rows(named=True)}
    for ts_key, final_row in final_map.items():
        for stage in list(SOURCE_STAGES.keys()) + ["final_wfa"]:
            src = final_row if stage == "final_wfa" else stage_maps.get(stage, {}).get(ts_key, {})
            f = flags.get(ts_key, {})
            rows.append({
                "run_id": run_id,
                "profile": profile,
                "symbol": symbol,
                "split": split,
                "timestamp": final_row.get("timestamp"),
                "source_stage": stage,
                "value_available": bool(src),
                "open": _float(src.get("open")),
                "high": _float(src.get("high")),
                "low": _float(src.get("low")),
                "close": _float(src.get("close")),
                "volume": _float(src.get("volume")),
                "target_15m_ret": _float(src.get("target_15m_ret", final_row.get("target_15m_ret") if stage == "final_wfa" else "")),
                "prediction": _float(final_row.get("prediction")) if stage == "final_wfa" else "",
                "position": _float(final_row.get("position_after", final_row.get("position"))) if stage == "final_wfa" else "",
                "pnl_increment": _float(final_row.get("net_pnl")) if stage == "final_wfa" else "",
                "session_id": str(src.get("session_id", "")),
                "session_date": str(src.get("session_date", "")),
                "session_boundary_flag": bool(f.get("session_boundary_flag", False)),
                "missing_bar_gap_flag": bool(f.get("missing_bar_gap_flag", False)),
                "extreme_return_flag": bool(f.get("extreme_return_flag", False)),
                "extreme_volume_flag": bool(f.get("extreme_volume_flag", False)),
            })
    return rows


def _top_bar_rows(
    run_id: str,
    profile: str,
    symbol: str,
    split: str,
    top: pl.DataFrame,
    stage_maps: dict[str, dict[str, dict[str, Any]]],
    feature_cols: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for r in top.iter_rows(named=True):
        ts_key = _ts_key(r["timestamp"])
        raw = stage_maps.get("raw", {}).get(ts_key, {})
        norm = stage_maps.get("session_normalized", {}).get(ts_key, {})
        labeled = stage_maps.get("labeled", {}).get(ts_key, {})
        features = {c: _float(r.get(c)) for c in feature_cols if c in r}
        rows.append({
            "run_id": run_id,
            "profile": profile,
            "symbol": symbol,
            "split": split,
            "pnl_rank": int(r.get("pnl_rank", 0)),
            "timestamp": r.get("timestamp"),
            "raw_ohlcv": _ohlcv(raw),
            "normalized_ohlcv": _ohlcv(norm),
            "labeled_target": _float(labeled.get("target_15m_ret", r.get("target_15m_ret"))),
            "frozen_feature_values": json.dumps(features, sort_keys=True),
            "prediction": _float(r.get("prediction")),
            "signal": _float(r.get("raw_signal")),
            "position": _float(r.get("position_after", r.get("position"))),
            "cost": _float(r.get("costs")),
            "net_pnl_contribution": _float(r.get("net_pnl")),
        })
    return rows


def _calendar_anomaly_rows(run_id: str, profile: str, symbol: str, split: str, df: pl.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ts = df["timestamp"].to_list()
    volumes = _series(df, "volume")
    vol_median = _float(volumes.median())
    vol_std = _float(volumes.std())
    vol_mean = _float(volumes.mean())
    for i, r in enumerate(df.iter_rows(named=True)):
        if i > 0:
            gap = _minutes_between(ts[i - 1], ts[i])
            if gap > 5:
                rows.append(_calendar_row(run_id, profile, symbol, split, r, "large_time_gap", gap, vol_median, f"gap_minutes={gap:.2f}"))
        if "session_id" in df.columns and i > 0 and r.get("session_id") != df["session_id"][i - 1]:
            rows.append(_calendar_row(run_id, profile, symbol, split, r, "session_boundary", 0.0, vol_median, "session_id changed"))
        if vol_std and abs((_float(r.get("volume")) - vol_mean) / vol_std) > 3:
            rows.append(_calendar_row(run_id, profile, symbol, split, r, "abnormal_volume", 0.0, vol_median, "volume_zscore_gt_3"))
    return rows


def _calendar_row(
    run_id: str,
    profile: str,
    symbol: str,
    split: str,
    row: dict[str, Any],
    anomaly_type: str,
    gap: float,
    median_volume: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "profile": profile,
        "symbol": symbol,
        "split": split,
        "timestamp": row.get("timestamp"),
        "session_id": str(row.get("session_id", "")),
        "session_date": str(row.get("session_date", "")),
        "anomaly_type": anomaly_type,
        "gap_minutes": gap,
        "volume": _float(row.get("volume")),
        "surrounding_median_volume": median_volume,
        "reason": reason,
    }


def _robust_alpha_row(
    run_id: str,
    profile: str,
    *,
    stage24_path: str | Path,
    breakdown_path: str | Path,
    threshold_outliers_path: str | Path,
) -> dict[str, Any]:
    breakdown = [
        r for r in read_json_rows(breakdown_path)
        if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile
    ]
    full_net = sum(_float(r.get("net_pnl")) for r in breakdown)
    es22 = [r for r in breakdown if str(r.get("symbol")) == "ES" and str(r.get("split")) == "22"]
    es22_net = sum(_float(r.get("net_pnl")) for r in es22)
    outlier_keys = _outlier_keys(breakdown, threshold_outliers_path, run_id, profile)
    outlier_net = sum(_float(r.get("net_pnl")) for r in breakdown if (str(r.get("symbol")), str(r.get("split"))) in outlier_keys)
    pnl = (
        pl.scan_parquet(stage24_path)
        .filter((pl.col("run_id") == run_id) & (pl.col("profile") == profile))
        .select(pl.col("net_pnl").cast(pl.Float64).fill_null(0.0))
        .collect()["net_pnl"]
        .to_list()
    )
    top_pos = sorted([x for x in pnl if x > 0], reverse=True)
    conclusion = "NO_ROBUST_ALPHA" if full_net - es22_net <= 0 or full_net - sum(top_pos[:10]) <= 0 else "REQUIRES_REVIEW"
    non_es22 = [r for r in breakdown if not (str(r.get("symbol")) == "ES" and str(r.get("split")) == "22")]
    non_outlier = [r for r in breakdown if (str(r.get("symbol")), str(r.get("split"))) not in outlier_keys]
    return {
        "run_id": run_id,
        "profile": profile,
        "full_net_pnl": full_net,
        "net_pnl_excluding_es_split_22": full_net - es22_net,
        "net_pnl_excluding_threshold_outliers": full_net - outlier_net,
        "net_pnl_excluding_top_1_pnl_bars": full_net - sum(top_pos[:1]),
        "net_pnl_excluding_top_5_pnl_bars": full_net - sum(top_pos[:5]),
        "net_pnl_excluding_top_10_pnl_bars": full_net - sum(top_pos[:10]),
        "ACCEPT": sum(1 for r in breakdown if str(r.get("acceptance_status")) == "ACCEPT"),
        "REJECT": sum(1 for r in breakdown if str(r.get("acceptance_status")) == "REJECT"),
        "accept_excluding_es_split_22": sum(1 for r in non_es22 if str(r.get("acceptance_status")) == "ACCEPT"),
        "reject_excluding_es_split_22": sum(1 for r in non_es22 if str(r.get("acceptance_status")) == "REJECT"),
        "accept_excluding_threshold_outliers": sum(1 for r in non_outlier if str(r.get("acceptance_status")) == "ACCEPT"),
        "reject_excluding_threshold_outliers": sum(1 for r in non_outlier if str(r.get("acceptance_status")) == "REJECT"),
        "conclusion": conclusion,
    }


def _outlier_keys(
    breakdown: list[dict[str, Any]],
    threshold_outliers_path: str | Path,
    run_id: str,
    profile: str,
) -> set[tuple[str, str]]:
    explicit = {
        (str(r.get("symbol")), str(r.get("split")))
        for r in read_json_rows(threshold_outliers_path)
        if str(r.get("run_id")) == run_id and str(r.get("profile")) == profile
    }
    if explicit:
        return explicit
    return {
        (str(r.get("symbol")), str(r.get("split")))
        for r in breakdown
        if _float(r.get("active_bar_pct")) > 0.03 or _float(r.get("turnover")) > 300
    }


def _row_flags(df: pl.DataFrame) -> dict[str, dict[str, bool]]:
    vol = _series(df, "volume")
    vol_mean = _float(vol.mean())
    vol_std = _float(vol.std())
    target = _series(df, "target_15m_ret")
    target_abs_q = _float(target.abs().quantile(0.99)) if len(target) else 0.0
    rows: dict[str, dict[str, bool]] = {}
    ts = df["timestamp"].to_list()
    for i, r in enumerate(df.iter_rows(named=True)):
        key = _ts_key(r.get("timestamp"))
        rows[key] = {
            "missing_bar_gap_flag": i > 0 and _minutes_between(ts[i - 1], ts[i]) > 5,
            "session_boundary_flag": bool("session_id" in df.columns and i > 0 and r.get("session_id") != df["session_id"][i - 1]),
            "extreme_return_flag": abs(_float(r.get("target_15m_ret"))) >= target_abs_q if target_abs_q else False,
            "extreme_volume_flag": bool(vol_std and abs((_float(r.get("volume")) - vol_mean) / vol_std) > 3),
        }
    return rows


def _feature_cols(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("feature_cols") or data.get("selected_features") or [])


def _ohlcv(row: dict[str, Any]) -> str:
    if not row:
        return ""
    return json.dumps({k: _float(row.get(k)) for k in ["open", "high", "low", "close", "volume"]}, sort_keys=True)


def _series(df: pl.DataFrame, col: str) -> pl.Series:
    if col not in df.columns:
        return pl.Series([], dtype=pl.Float64)
    return df[col].cast(pl.Float64, strict=False).fill_null(0.0)


def _minutes_between(a: Any, b: Any) -> float:
    try:
        return float((b - a).total_seconds()) / 60.0
    except Exception:
        return 0.0


def _year(ts: Any) -> int | None:
    if isinstance(ts, datetime):
        return ts.year
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).year
    except Exception:
        return None


def _ts_key(ts: Any) -> str:
    if isinstance(ts, datetime):
        return ts.isoformat()
    return str(ts)


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
