from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

import polars as pl

from pipeline.features.frozen import _candidate_features, _excluded_columns, _scoped_parquet_paths
from pipeline.validation.diagnostic_io import write_csv_json


FROZEN_FEATURE_AUDIT_CSV = Path("reports/validation/frozen_feature_audit.csv")
FROZEN_FEATURE_AUDIT_JSON = Path("reports/validation/frozen_feature_audit.json")
CANDIDATE_COVERAGE_CSV = Path("reports/validation/candidate_feature_coverage.csv")
CANDIDATE_COVERAGE_JSON = Path("reports/validation/candidate_feature_coverage.json")
SELECTION_SENSITIVITY_CSV = Path("reports/validation/feature_selection_sensitivity.csv")
SELECTION_SENSITIVITY_JSON = Path("reports/validation/feature_selection_sensitivity.json")

FROZEN_AUDIT_FIELDS = [
    "feature", "selection_status", "rank", "score", "ic_mean", "ic_median", "ic_std",
    "stability_score", "fold_pass_count", "correlation_cluster", "rejection_reason",
    "leakage_flag", "missing_pct", "zero_variance_flag",
]
COVERAGE_FIELDS = [
    "feature", "exists_in_matrix", "missing_pct", "nonnull_count", "mean", "std", "min",
    "max", "zero_variance_flag", "available_symbols", "available_years",
]
SENSITIVITY_FIELDS = [
    "scenario", "selected_count", "selected_features", "rejected_leakage_count",
    "max_pairwise_corr", "median_pairwise_corr", "feature_families",
]


def write_frozen_feature_diagnostics(
    *,
    config: Any,
    frozen_root: str | Path = "data/frozen_features/phase5_v1",
    source_feature_matrix_root: str | Path = "data/feature_matrices/expanded",
) -> dict[str, Any]:
    frozen_root = Path(frozen_root)
    matrix_root = Path(source_feature_matrix_root)
    target_col = str(getattr(getattr(config, "walkforward", object()), "walkforward_target", "target_15m_ret"))
    paths = _scoped_parquet_paths(matrix_root, config)
    if not paths:
        raise RuntimeError(f"FROZEN FEATURE AUDIT FAIL: no matrix parquet under {matrix_root}")

    schema = pl.scan_parquet(paths[0]).collect_schema()
    matrix_cols = schema.names()
    candidates = _candidate_features(schema)
    excluded = set(_excluded_columns(matrix_cols, target_col))
    selected = _read_selected(frozen_root / "selected_features.csv")
    rejected = _read_rejected(frozen_root / "rejected_features.csv")
    feature_cols = _read_feature_cols(frozen_root / "feature_cols.json")
    selected_features = [str(r["feature"]) for r in selected] if selected else feature_cols
    selected_meta = {r["feature"]: r for r in selected}
    rejected_meta = {r["feature"]: r for r in rejected}

    candidate_coverage = [_coverage_row(f, paths) for f in sorted(set(candidates) | set(selected_features) | set(rejected_meta))]
    write_csv_json(candidate_coverage, csv_path=CANDIDATE_COVERAGE_CSV, json_path=CANDIDATE_COVERAGE_JSON, fields=COVERAGE_FIELDS)

    audit_features = sorted(set(candidates) | set(selected_features) | set(rejected_meta) | {c for c in excluded if _is_numeric(schema, c)})
    audit_rows = []
    for feature in audit_features:
        cov = _coverage_row(feature, paths)
        ics = _feature_ics(feature, paths, target_col) if feature in matrix_cols and _is_numeric(schema, feature) else []
        selected_flag = feature in selected_features
        leakage = feature in excluded or feature.startswith(("future_", "target_", "label_"))
        rejection_reason = ""
        if selected_flag:
            selection_status = "selected"
        else:
            selection_status = "rejected"
            rejection_reason = str(rejected_meta.get(feature, {}).get("reason") or ("excluded_leakage_or_metadata" if leakage else "not_in_frozen_set"))
        audit_rows.append({
            "feature": feature,
            "selection_status": selection_status,
            "rank": selected_meta.get(feature, {}).get("rank", ""),
            "score": selected_meta.get(feature, {}).get("score", rejected_meta.get(feature, {}).get("score", "")),
            "ic_mean": _safe_mean(ics),
            "ic_median": _safe_median(ics),
            "ic_std": _safe_std(ics),
            "stability_score": _stability_score(ics),
            "fold_pass_count": len(ics),
            "correlation_cluster": _feature_family(feature),
            "rejection_reason": rejection_reason,
            "leakage_flag": bool(leakage),
            "missing_pct": cov["missing_pct"],
            "zero_variance_flag": cov["zero_variance_flag"],
        })
    write_csv_json(audit_rows, csv_path=FROZEN_FEATURE_AUDIT_CSV, json_path=FROZEN_FEATURE_AUDIT_JSON, fields=FROZEN_AUDIT_FIELDS)

    ranked = sorted(
        [r for r in audit_rows if r["feature"] in candidates and not r["leakage_flag"] and not r["zero_variance_flag"]],
        key=lambda r: (-_float(r["score"] if r["score"] != "" else abs(_float(r["ic_mean"]))), r["feature"]),
    )
    sensitivity = _sensitivity_rows(ranked, paths, len([r for r in audit_rows if r["leakage_flag"]]))
    write_csv_json(sensitivity, csv_path=SELECTION_SENSITIVITY_CSV, json_path=SELECTION_SENSITIVITY_JSON, fields=SENSITIVITY_FIELDS)
    return {
        "candidate_count": len(candidates),
        "selected_count": len(selected_features),
        "rejected_count": len(rejected),
        "leakage_or_metadata_rejected_count": len([r for r in audit_rows if r["leakage_flag"]]),
        "frozen_audit_rows": len(audit_rows),
        "candidate_coverage_rows": len(candidate_coverage),
        "sensitivity_rows": len(sensitivity),
    }


def _read_selected(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("feature")]


def _read_rejected(path: Path) -> list[dict[str, Any]]:
    return _read_selected(path)


def _read_feature_cols(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [str(x) for x in (payload.get("feature_cols") or payload.get("selected_features") or [])]


def _coverage_row(feature: str, paths: list[Path]) -> dict[str, Any]:
    symbols = sorted({p.parent.name for p in paths if _path_has_col(p, feature)})
    years = sorted({p.stem for p in paths if _path_has_col(p, feature)})
    if not symbols:
        return {
            "feature": feature, "exists_in_matrix": False, "missing_pct": "", "nonnull_count": 0,
            "mean": "", "std": "", "min": "", "max": "", "zero_variance_flag": "",
            "available_symbols": "", "available_years": "",
        }
    lf = pl.scan_parquet([p for p in paths if _path_has_col(p, feature)]).select(pl.col(feature).cast(pl.Float64, strict=False).alias(feature))
    stats = lf.select(
        pl.len().alias("n"),
        pl.col(feature).null_count().alias("nulls"),
        pl.col(feature).count().alias("nonnull"),
        pl.col(feature).mean().alias("mean"),
        pl.col(feature).std().alias("std"),
        pl.col(feature).min().alias("min"),
        pl.col(feature).max().alias("max"),
    ).collect().row(0, named=True)
    std = _float(stats.get("std"))
    return {
        "feature": feature,
        "exists_in_matrix": True,
        "missing_pct": _safe_div(_float(stats.get("nulls")), _float(stats.get("n"))),
        "nonnull_count": int(_float(stats.get("nonnull"))),
        "mean": _float(stats.get("mean")),
        "std": std,
        "min": _float(stats.get("min")),
        "max": _float(stats.get("max")),
        "zero_variance_flag": bool(std == 0.0),
        "available_symbols": ",".join(symbols),
        "available_years": ",".join(years),
    }


def _feature_ics(feature: str, paths: list[Path], target_col: str) -> list[float]:
    vals = []
    for path in paths:
        if not _path_has_col(path, feature) or not _path_has_col(path, target_col):
            continue
        try:
            val = pl.scan_parquet(path).select(pl.corr(feature, target_col).alias("ic")).collect()["ic"][0]
            if val is not None and val == val:
                vals.append(float(val))
        except Exception:
            continue
    return vals


def _sensitivity_rows(ranked: list[dict[str, Any]], paths: list[Path], rejected_leakage_count: int) -> list[dict[str, Any]]:
    rows = []
    for scenario, n in [("top_4", 4), ("top_8", 8), ("top_16", 16), ("top_32", 32), ("all_passed_stability", len(ranked))]:
        features = [str(r["feature"]) for r in ranked[:n]]
        pairwise = _pairwise_abs_corr(features, paths)
        rows.append({
            "scenario": scenario,
            "selected_count": len(features),
            "selected_features": ",".join(features),
            "rejected_leakage_count": rejected_leakage_count,
            "max_pairwise_corr": max(pairwise) if pairwise else 0.0,
            "median_pairwise_corr": float(median(pairwise)) if pairwise else 0.0,
            "feature_families": ",".join(sorted({_feature_family(f) for f in features})),
        })
    return rows


def _pairwise_abs_corr(features: list[str], paths: list[Path]) -> list[float]:
    vals = []
    for i, left in enumerate(features):
        for right in features[i + 1:]:
            try:
                val = pl.scan_parquet(paths).select(pl.corr(left, right).alias("corr")).collect()["corr"][0]
                if val is not None and val == val:
                    vals.append(abs(float(val)))
            except Exception:
                continue
    return vals


def _path_has_col(path: Path, col: str) -> bool:
    try:
        return col in pl.scan_parquet(path).collect_schema().names()
    except Exception:
        return False


def _is_numeric(schema: pl.Schema, col: str) -> bool:
    try:
        return schema[col].is_numeric()
    except Exception:
        return False


def _feature_family(feature: str) -> str:
    if feature.startswith("ret_lag_"):
        return "returns_lag"
    if feature.startswith("roll_vol_"):
        return "rolling_volatility"
    if feature.startswith("roll_volume_"):
        return "rolling_volume"
    if feature.startswith("roll_range_"):
        return "rolling_range"
    if feature.startswith(("target_", "label_", "future_")):
        return "leakage_or_label"
    if feature in {"open", "high", "low", "close", "volume"}:
        return "price_volume_metadata"
    return feature.split("_", 1)[0] if "_" in feature else "other"


def _stability_score(values: list[float]) -> float:
    if not values:
        return 0.0
    med = median(values)
    if med == 0:
        return 0.0
    sign = 1 if med > 0 else -1
    return sum(1 for v in values if (v > 0) == (sign > 0)) / len(values)


def _safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _safe_median(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    return float((sum((v - mu) ** 2 for v in values) / (len(values) - 1)) ** 0.5)


def _safe_div(num: float, den: float) -> float:
    return 0.0 if den == 0 else float(num) / float(den)


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
