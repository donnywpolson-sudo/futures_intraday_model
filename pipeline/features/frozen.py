from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.features.registry import FORBIDDEN_PREFIXES, METADATA, SAFE_ROLL_FEATURE_PREFIXES, TARGET_PREFIXES
from pipeline.validation.diagnostic_io import write_csv_json


FROZEN_FEATURE_ROOT = Path("data/frozen_features/phase5_v1")
FEATURE_COLS_JSON = FROZEN_FEATURE_ROOT / "feature_cols.json"
SELECTED_FEATURES_CSV = FROZEN_FEATURE_ROOT / "selected_features.csv"
REJECTED_FEATURES_CSV = FROZEN_FEATURE_ROOT / "rejected_features.csv"
MANIFEST_JSON = FROZEN_FEATURE_ROOT / "manifest.json"
EXTRA_METADATA_COLS = {"session_bar_index"}
STAGE22_AUDIT_CSV = Path("reports/validation/stage_22_train_only_selection_audit_report.csv")
STAGE22_AUDIT_JSON = Path("reports/validation/stage_22_train_only_selection_audit_report.json")
STAGE22_FIELDS = [
    "run_id", "profile", "created_at", "source_feature_matrix", "source_feature_matrix_hash",
    "target_col", "train_only", "ranking_method", "selected_candidate_count",
    "rejected_candidate_count", "eligible_candidate_count", "leakage_rejected_count",
    "metadata_rejected_count", "zero_variance_rejected_count", "correlation_rejected_count",
    "stability_rejected_count", "feature", "eligible", "selected", "rank", "score",
    "ic_mean", "ic_median", "ic_std", "stability_score", "fold_pass_count", "missing_pct",
    "zero_variance_flag", "max_abs_corr_to_selected", "rejection_reason",
]


def create_frozen_feature_set(
    *,
    config: Any,
    run_id: str,
    profile: str,
    source_feature_matrix_root: str | Path = "data/feature_matrices/expanded",
    source_ranking_artifact: str | Path = "reports/validation/stage_22_train_only_selection_audit_report.json",
    output_root: str | Path = FROZEN_FEATURE_ROOT,
) -> dict[str, Any]:
    root = Path(source_feature_matrix_root)
    output_root = Path(output_root)
    target_col = str(getattr(getattr(config, "walkforward", object()), "walkforward_target", "target_15m_ret"))
    paths = _scoped_parquet_paths(root, config)
    if not paths:
        raise RuntimeError(f"FROZEN FEATURE SET FAIL: no expanded feature matrix parquet under {root}")
    schema = pl.scan_parquet(paths[0]).collect_schema()
    candidates = _candidate_features(schema)
    if not candidates:
        raise RuntimeError("FROZEN FEATURE SET FAIL: no eligible numeric features")
    train_end = _train_end_from_first_window(paths, config)
    selected_rows, rejected_rows = _rank_train_only(paths, candidates, target_col, train_end, config)
    selected = [r["feature"] for r in selected_rows]
    if not selected:
        raise RuntimeError("FROZEN FEATURE SET FAIL: selected_feature_count=0")
    _write_stage22_audit(
        run_id=run_id,
        profile=profile,
        paths=paths,
        candidates=candidates,
        selected_rows=selected_rows,
        rejected_rows=rejected_rows,
        target_col=target_col,
        train_end=train_end,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    feature_cols_path = output_root / "feature_cols.json"
    selected_path = output_root / "selected_features.csv"
    rejected_path = output_root / "rejected_features.csv"
    manifest_path = output_root / "manifest.json"
    metadata_cols = sorted(set(METADATA) | EXTRA_METADATA_COLS)
    excluded_cols = sorted(set(_excluded_columns(schema.names(), target_col)))
    leakage = _leakage_check(selected, schema.names(), target_col)
    manifest = {
        "run_id": run_id,
        "profile": profile,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_feature_matrix_root": str(root),
        "source_ranking_artifact": str(source_ranking_artifact),
        "selected_feature_count": len(selected_rows),
        "rejected_feature_count": len(rejected_rows),
        "target_col": target_col,
        "metadata_cols": metadata_cols,
        "excluded_cols": excluded_cols,
        "selection_method": "train_only_abs_corr_first_wfa_train_window",
        "train_only": True,
        "leakage_check": "PASS" if leakage["status"] == "PASS" else "FAIL",
        "config_hash": _config_hash(config),
        "train_end": str(train_end),
        "feature_cols_path": str(feature_cols_path),
        "selected_features_path": str(selected_path),
        "rejected_features_path": str(rejected_path),
    }
    atomic_write_json(feature_cols_path, {"feature_cols": selected, "selected_features": selected, "manifest": str(manifest_path)})
    write_csv_rows(selected_path, selected_rows)
    write_csv_rows(rejected_path, rejected_rows)
    atomic_write_json(manifest_path, manifest)
    return validate_frozen_feature_set(output_root=output_root, source_feature_matrix_root=root, config=config)


def validate_frozen_feature_set(
    *,
    output_root: str | Path = FROZEN_FEATURE_ROOT,
    source_feature_matrix_root: str | Path = "data/feature_matrices/expanded",
    config: Any,
) -> dict[str, Any]:
    output_root = Path(output_root)
    feature_cols_path = output_root / "feature_cols.json"
    selected_path = output_root / "selected_features.csv"
    rejected_path = output_root / "rejected_features.csv"
    manifest_path = output_root / "manifest.json"
    missing = [str(p) for p in (feature_cols_path, selected_path, rejected_path, manifest_path) if not p.exists()]
    if missing:
        return {"status": "MISSING", "reason": "missing artifacts: " + ",".join(missing)}
    try:
        feature_payload = json.loads(feature_cols_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "FAIL", "reason": f"invalid json: {exc}"}
    selected = list(feature_payload.get("feature_cols") or feature_payload.get("selected_features") or [])
    if not selected:
        return {"status": "FAIL", "reason": "selected feature count is zero"}
    if manifest.get("train_only") is not True:
        return {"status": "FAIL", "reason": "manifest train_only is not true"}
    if str(manifest.get("leakage_check")) != "PASS":
        return {"status": "FAIL", "reason": "manifest leakage_check is not PASS"}
    root = Path(source_feature_matrix_root)
    paths = _scoped_parquet_paths(root, config)
    if not paths:
        return {"status": "FAIL", "reason": f"no feature matrix parquet under {root}"}
    schema = pl.scan_parquet(paths[0]).collect_schema()
    leakage = _leakage_check(selected, schema.names(), str(manifest.get("target_col") or "target_15m_ret"))
    if leakage["status"] != "PASS":
        return leakage
    return {
        "status": "PASS",
        "reason": "ok",
        "selected_feature_count": len(selected),
        "manifest": str(manifest_path),
    }


def _scoped_parquet_paths(root: Path, config: Any) -> list[Path]:
    symbols = {str(s) for s in getattr(config, "symbols", []) or []}
    start_year = getattr(config, "start_year", None)
    end_year = getattr(config, "end_year", None)
    out = []
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
        out.append(path)
    return out


def _candidate_features(schema: pl.Schema) -> list[str]:
    return [
        c for c, dtype in zip(schema.names(), schema.dtypes())
        if dtype.is_numeric() and c not in _excluded_columns(schema.names(), "target_15m_ret")
    ]


def _excluded_columns(cols: list[str], target_col: str) -> list[str]:
    excluded = []
    for c in cols:
        if c == target_col or c.startswith(TARGET_PREFIXES) or c in METADATA or c in EXTRA_METADATA_COLS:
            excluded.append(c)
        elif c.startswith(FORBIDDEN_PREFIXES):
            excluded.append(c)
        elif c.startswith("roll_") and not c.startswith(SAFE_ROLL_FEATURE_PREFIXES):
            excluded.append(c)
    return excluded


def _train_end_from_first_window(paths: list[Path], config: Any) -> Any:
    min_ts = pl.scan_parquet(paths).select(pl.col("ts_event").min().alias("min_ts")).collect()["min_ts"][0]
    train_days = int(getattr(getattr(config, "walkforward", object()), "wf_train_days", 120) or 120)
    if hasattr(min_ts, "date"):
        return min_ts + timedelta(days=train_days)
    return min_ts


def _rank_train_only(paths: list[Path], candidates: list[str], target_col: str, train_end: Any, config: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    max_features = int(getattr(getattr(config, "discovery", object()), "max_selected_features", 1000) or 1000)
    lf = (
        pl.scan_parquet(paths)
        .filter(pl.col("ts_event") < train_end)
        .filter(pl.col(target_col).is_not_null())
    )
    rankings = []
    rejected = []
    for feature in candidates:
        try:
            val = lf.select(pl.corr(feature, target_col).alias("score")).collect()["score"][0]
        except Exception:
            val = None
        if val is None or val != val:
            rejected.append({"feature": feature, "reason": "null_train_corr", "score": ""})
        else:
            rankings.append({"feature": feature, "score": abs(float(val)), "reason": ""})
    rankings.sort(key=lambda r: (-float(r["score"]), r["feature"]))
    selected = [
        {"rank": i + 1, "feature": r["feature"], "score": r["score"], "reason": "selected_train_abs_corr"}
        for i, r in enumerate(rankings[:max_features])
    ]
    rejected.extend(
        {"feature": r["feature"], "reason": "below_selection_cut", "score": r["score"]}
        for r in rankings[max_features:]
    )
    return selected, rejected


def _write_stage22_audit(
    *,
    run_id: str,
    profile: str,
    paths: list[Path],
    candidates: list[str],
    selected_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    target_col: str,
    train_end: Any,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    selected_features = [str(r["feature"]) for r in selected_rows]
    selected_meta = {str(r["feature"]): r for r in selected_rows}
    rejected_meta = {str(r["feature"]): r for r in rejected_rows}
    feature_rows = []
    for feature in sorted(set(candidates) | set(selected_meta) | set(rejected_meta)):
        ics = _feature_ics(feature, paths, target_col, train_end)
        stats = _feature_stats(feature, paths, train_end)
        selected = feature in selected_meta
        feature_rows.append({
            "feature": feature,
            "eligible": feature in candidates,
            "selected": selected,
            "rank": selected_meta.get(feature, {}).get("rank", ""),
            "score": selected_meta.get(feature, {}).get("score", rejected_meta.get(feature, {}).get("score", "")),
            "ic_mean": _mean(ics),
            "ic_median": _median(ics),
            "ic_std": _std(ics),
            "stability_score": _stability(ics),
            "fold_pass_count": len(ics),
            "missing_pct": stats["missing_pct"],
            "zero_variance_flag": stats["zero_variance_flag"],
            "max_abs_corr_to_selected": _max_abs_corr_to_selected(feature, selected_features, paths, train_end),
            "rejection_reason": "" if selected else str(rejected_meta.get(feature, {}).get("reason") or "not_selected"),
        })
    zero_var_rejected = sum(1 for r in feature_rows if (not r["selected"]) and r["zero_variance_flag"])
    summary = {
        "run_id": run_id,
        "profile": profile,
        "created_at": created_at,
        "source_feature_matrix": ";".join(str(p) for p in paths),
        "source_feature_matrix_hash": _source_hash(paths),
        "target_col": target_col,
        "train_only": True,
        "ranking_method": "train_only_abs_corr_first_wfa_train_window",
        "selected_candidate_count": len(selected_rows),
        "rejected_candidate_count": len(rejected_rows),
        "eligible_candidate_count": len(candidates),
        "leakage_rejected_count": 0,
        "metadata_rejected_count": 0,
        "zero_variance_rejected_count": zero_var_rejected,
        "correlation_rejected_count": 0,
        "stability_rejected_count": 0,
    }
    rows = [{**summary, **r} for r in sorted(feature_rows, key=lambda r: (not r["selected"], int(r["rank"] or 999999), r["feature"]))]
    write_csv_json(rows, csv_path=STAGE22_AUDIT_CSV, json_path=STAGE22_AUDIT_JSON, fields=STAGE22_FIELDS)


def _leakage_check(selected: list[str], matrix_cols: list[str], target_col: str) -> dict[str, Any]:
    missing = [c for c in selected if c not in matrix_cols]
    if missing:
        return {"status": "FAIL", "reason": "selected features missing from matrix: " + ",".join(missing[:10])}
    bad = [c for c in selected if c in _excluded_columns(matrix_cols, target_col)]
    if bad:
        return {"status": "FAIL", "reason": "selected features include forbidden columns: " + ",".join(bad)}
    return {"status": "PASS", "reason": "ok"}


def _feature_ics(feature: str, paths: list[Path], target_col: str, train_end: Any) -> list[float]:
    vals = []
    for path in paths:
        try:
            val = (
                pl.scan_parquet(path)
                .filter(pl.col("ts_event") < train_end)
                .filter(pl.col(target_col).is_not_null())
                .select(pl.corr(feature, target_col).alias("ic"))
                .collect()["ic"][0]
            )
            if val is not None and val == val:
                vals.append(float(val))
        except Exception:
            continue
    return vals


def _feature_stats(feature: str, paths: list[Path], train_end: Any) -> dict[str, Any]:
    try:
        stats = (
            pl.scan_parquet(paths)
            .filter(pl.col("ts_event") < train_end)
            .select(
                pl.len().alias("n"),
                pl.col(feature).null_count().alias("nulls"),
                pl.col(feature).cast(pl.Float64, strict=False).std().alias("std"),
            )
            .collect()
            .row(0, named=True)
        )
    except Exception:
        return {"missing_pct": "", "zero_variance_flag": ""}
    n = float(stats.get("n") or 0)
    nulls = float(stats.get("nulls") or 0)
    std = float(stats.get("std") or 0.0)
    return {"missing_pct": 0.0 if n == 0 else nulls / n, "zero_variance_flag": bool(std == 0.0)}


def _max_abs_corr_to_selected(feature: str, selected: list[str], paths: list[Path], train_end: Any) -> float:
    vals = []
    for other in selected:
        if other == feature:
            continue
        try:
            val = (
                pl.scan_parquet(paths)
                .filter(pl.col("ts_event") < train_end)
                .select(pl.corr(feature, other).alias("corr"))
                .collect()["corr"][0]
            )
            if val is not None and val == val:
                vals.append(abs(float(val)))
        except Exception:
            continue
    return max(vals) if vals else 0.0


def _source_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths):
        stat = path.stat()
        h.update(str(path).encode("utf-8"))
        h.update(str(stat.st_size).encode("utf-8"))
        h.update(str(stat.st_mtime_ns).encode("utf-8"))
    return h.hexdigest()


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    vals = sorted(vals)
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mu = _mean(vals)
    return (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


def _stability(vals: list[float]) -> float:
    if not vals:
        return 0.0
    med = _median(vals)
    if med == 0:
        return 0.0
    return sum(1 for v in vals if (v > 0) == (med > 0)) / len(vals)


def _config_hash(config: Any) -> str:
    try:
        payload = config.model_dump()
    except Exception:
        payload = str(config)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
