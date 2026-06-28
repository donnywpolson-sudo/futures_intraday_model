#!/usr/bin/env python3
"""Phase 4 derived lineage and raw-vs-derived audit."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.audit_databento_common import (
    Blocker,
    PhaseResult,
    blocker_from_mutation,
    compare_source_manifests,
    phase_gate_path,
    read_json_if_exists,
    rel,
    repo_path,
    source_manifest_rows,
    utc_now,
    write_csv,
    write_json,
    write_phase_outputs,
    write_source_manifest,
    write_text,
)


PHASE = "phase4"
TARGET_DERIVED_ROOTS = [
    "data/validated",
    "data/session_normalized",
    "data/raw",
    "data/causally_gated_normalized",
    "data/labeled",
    "data/feature_matrices",
    "data/predictions",
]
CURRENT_MODELING_ROOTS = {"data/causally_gated_normalized", "data/feature_matrices/baseline"}
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
KEY_COLUMNS = ["ts", "ts_event", "market", "year", "instrument_id"]
FORBIDDEN_FEATURE_PREFIXES = ("target_", "label_", "future_", "feature_future_", "feature_label_")
READ_HINTS = ("read", "load", "glob", "exists", "input", "root", "parquet", "csv", "json")
WRITE_HINTS = ("write", "to_parquet", "to_csv", "output", "mkdir", "manifest", "report")


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value) not in {"", "None", "nan"}})


def parse_market_year(path: Path) -> tuple[str, str]:
    if path.suffix != ".parquet":
        return "", ""
    year = path.stem if path.stem.isdigit() else ""
    market = path.parent.name if year else ""
    return market, year


def parquet_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.parquet") if path.is_file())


def json_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def file_count(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def parquet_schema(path: Path) -> tuple[list[str], int, str]:
    try:
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        return list(parquet.schema_arrow.names), int(parquet.metadata.num_rows), "ok"
    except Exception as exc:  # pragma: no cover - depends on optional parquet runtime failures.
        return [], 0, f"metadata_error:{type(exc).__name__}:{exc}"


def parquet_sample(path: Path, columns: list[str], *, max_rows: int = 500) -> tuple[pd.DataFrame, str]:
    try:
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        available = [column for column in columns if column in parquet.schema_arrow.names]
        if not available or parquet.metadata.num_row_groups == 0:
            return pd.DataFrame(), "no_available_columns"
        frame = parquet.read_row_group(0, columns=available).to_pandas()
        return frame.head(max_rows).copy(), "ok"
    except Exception as exc:  # pragma: no cover - depends on optional parquet runtime failures.
        return pd.DataFrame(), f"sample_error:{type(exc).__name__}:{exc}"


def inventory_pairs(inventory_rows: list[dict[str, Any]], schema: str = "ohlcv-1m") -> set[tuple[str, str]]:
    return {
        (str(row.get("market", "")), str(row.get("year", "")))
        for row in inventory_rows
        if row.get("schema") == schema and row.get("market") and row.get("year")
    }


def parquet_pairs(root: Path) -> set[tuple[str, str]]:
    return {pair for pair in (parse_market_year(path) for path in parquet_files(root)) if pair != ("", "")}


def parse_paths_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    in_paths = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("paths:"):
            in_paths = True
            continue
        if in_paths and line and not line.startswith(" "):
            break
        if in_paths:
            match = re.match(r"\s{2}([A-Za-z0-9_]+):\s*(.+?)\s*$", line)
            if match:
                raw_value = match.group(2).strip().strip('"').strip("'")
                values[match.group(1)] = "" if raw_value.lower() in {"null", "none", "~"} else raw_value
    return values


def infer_reference_operation(context: str) -> str:
    lower = context.lower()
    if any(hint in lower for hint in WRITE_HINTS) and not any(hint in lower for hint in ("read", "input")):
        return "write"
    if any(hint in lower for hint in READ_HINTS):
        return "read"
    return "reference"


def is_active_reference(file_path: str) -> bool:
    return file_path.startswith("scripts/") or file_path.startswith("configs/")


def stage_for_root(root: str) -> str:
    if root == "data/raw":
        return "derived_raw_parquet"
    if root == "data/validated":
        return "validated"
    if root == "data/session_normalized":
        return "session_normalized"
    if root == "data/causally_gated_normalized":
        return "causally_gated_modeling_base"
    if root.startswith("data/causally_gated_normalized_pre_replace"):
        return "causal_backup"
    if root == "data/labeled":
        return "labels"
    if root == "data/feature_matrices" or root.startswith("data/feature_matrices/"):
        return "features"
    if root == "data/predictions" or root.startswith("data/predictions/"):
        return "predictions"
    return "derived_or_unknown"


def expected_source_for_stage(stage: str) -> str:
    return {
        "derived_raw_parquet": "data/dbn",
        "validated": "data/raw",
        "session_normalized": "data/raw",
        "causally_gated_modeling_base": "data/raw",
        "causal_backup": "data/raw",
        "labels": "data/causally_gated_normalized",
        "features": "data/labeled",
        "predictions": "data/feature_matrices/baseline",
    }.get(stage, "")


def manifest_paths(root: Path) -> list[str]:
    names = [path for path in json_files(root) if "manifest" in path.name.lower()]
    return [rel(path) for path in names[:10]]


def folder_lineage_rows(folder_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roots = set(TARGET_DERIVED_ROOTS)
    for row in folder_rows:
        path = str(row.get("path", ""))
        classification = str(row.get("classification", ""))
        if not path.startswith("data/") or path.startswith("data/dbn"):
            continue
        if classification in {"current_derived", "quarantine_candidate", "unsafe_unknown"}:
            roots.add(path)
    rows: list[dict[str, Any]] = []
    for root_text in sorted(roots):
        root = repo_path(root_text)
        parquets = parquet_files(root)
        markets_years = [parse_market_year(path) for path in parquets]
        markets = unique_sorted(market for market, _ in markets_years)
        years = unique_sorted(year for _, year in markets_years)
        stat_times = [path.stat().st_mtime for path in parquets[:1000]] if root.exists() else []
        sample_columns: list[str] = []
        sample_rows = 0
        schema_status = "not_applicable"
        if parquets:
            sample_columns, sample_rows, schema_status = parquet_schema(parquets[0])
        stage = stage_for_root(root_text)
        classification = next((row.get("classification", "") for row in folder_rows if row.get("path") == root_text), "")
        if not classification:
            classification = "current_derived" if root_text in TARGET_DERIVED_ROOTS and root.exists() else "missing_expected"
        trace_columns = {"source_file", "source_sha256", "source_path", "source_file_hash"} & set(sample_columns)
        traces_to_raw = bool(root.exists() and (root_text == "data/raw" or trace_columns or stage in {"labels", "features", "predictions"}))
        current_status = "missing" if not root.exists() else "quarantine_candidate" if classification == "quarantine_candidate" else "current_or_reviewed"
        if root_text in {"data/labeled", "data/feature_matrices", "data/predictions"}:
            current_status = "stale_or_requires_rebuild_review"
        rows.append(
            {
                "folder": root_text,
                "stage": stage,
                "classification": classification,
                "exists": root.exists(),
                "source_folder": expected_source_for_stage(stage),
                "generating_script": generating_script_for_stage(stage),
                "config_used": "configs/alpha_tiered.yaml" if stage != "derived_or_unknown" else "",
                "manifest_present": bool(manifest_paths(root)),
                "manifest_paths": "|".join(manifest_paths(root)),
                "file_count": file_count(root),
                "parquet_count": len(parquets),
                "markets_count": len(markets),
                "markets": "|".join(markets),
                "years_count": len(years),
                "years": "|".join(years),
                "sample_schema_status": schema_status,
                "sample_row_count": sample_rows,
                "sample_columns": "|".join(sample_columns[:60]),
                "trace_to_canonical_raw_dbn": traces_to_raw,
                "current_status": current_status,
                "safe_as_model_input": "yes_with_caveats" if root_text == "data/causally_gated_normalized" and traces_to_raw else "no",
                "evidence": "schema_has_source_lineage_columns" if trace_columns else "folder_inventory_and_config_reference",
            }
        )
    return rows


def generating_script_for_stage(stage: str) -> str:
    return {
        "derived_raw_parquet": "scripts/validation or phase1 raw parquet builders",
        "validated": "",
        "session_normalized": "scripts/phase2_causal_base/build_causal_base_data.py",
        "causally_gated_modeling_base": "scripts/phase2_causal_base/build_causal_base_data.py",
        "labels": "scripts/phase3_labels/build_labels.py",
        "features": "scripts/phase4_features/build_baseline_features.py",
        "predictions": "scripts/phase8_model_selection/evaluate_predictions.py",
        "causal_backup": "scripts/phase2_causal_base/build_causal_base_data.py",
    }.get(stage, "")


def active_pipeline_rows(data_refs: list[dict[str, Any]], config_paths: dict[str, str], quarantine_paths: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    role_map = {
        "raw_root": "expected_derived_raw_folder",
        "causal_base_root": "expected_causally_gated_modeling_input_folder",
        "labeled_root": "expected_label_folder",
        "feature_matrix_root": "expected_feature_matrix_folder",
        "predictions_root": "expected_predictions_folder",
    }
    for name, path in sorted(config_paths.items()):
        is_missing_required = name == "predictions_root" and not path
        rows.append(
            {
                "item_type": "active_config_path",
                "name": name,
                "path": path,
                "role": role_map.get(name, "configured_path"),
                "source_file": "configs/alpha_tiered.yaml",
                "line": "",
                "operation": "config",
                "context": "",
                "status": "not_configured" if is_missing_required else "ok",
                "issue": "predictions_root not configured; explicit root required" if is_missing_required else "",
                "evidence": "configs/alpha_tiered.yaml paths block",
            }
        )
    for row in data_refs:
        file_path = str(row.get("file", ""))
        if not is_active_reference(file_path):
            continue
        path_ref = str(row.get("reference", ""))
        context = str(row.get("context", ""))
        operation = infer_reference_operation(context)
        stale = any(path_ref == q or path_ref.startswith(q + "/") for q in quarantine_paths)
        status = "stale_or_quarantine_reference" if stale else "ok"
        rows.append(
            {
                "item_type": "path_reference",
                "name": "",
                "path": path_ref,
                "role": "read_or_write_path",
                "source_file": file_path,
                "line": row.get("line", ""),
                "operation": operation,
                "context": context,
                "status": status,
                "issue": "active script/config references quarantine candidate" if stale else "",
                "evidence": f"{file_path}:{row.get('line', '')}",
            }
        )
    return rows


def raw_vs_derived_rows(raw_pairs: set[tuple[str, str]], canonical_pairs: set[tuple[str, str]], roots: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, root in roots.items():
        pairs = parquet_pairs(root)
        if not root.exists():
            rows.append(
                {
                    "derived_root": rel(root),
                    "comparison": "missing_folder",
                    "derived_pairs": 0,
                    "raw_pairs": len(raw_pairs),
                    "canonical_ohlcv_pairs": len(canonical_pairs),
                    "missing_vs_raw": 0,
                    "extra_vs_raw": 0,
                    "missing_vs_canonical": 0,
                    "extra_vs_canonical": 0,
                    "status": "not_applicable",
                    "evidence": "folder_missing",
                }
            )
            continue
        missing_vs_raw = sorted(raw_pairs - pairs)
        extra_vs_raw = sorted(pairs - raw_pairs)
        missing_vs_canonical = sorted(canonical_pairs - pairs)
        extra_vs_canonical = sorted(pairs - canonical_pairs)
        status = "pass" if not extra_vs_raw else "review"
        if name in {"labeled", "feature_matrices", "predictions"}:
            status = "stale_or_partial_review"
        rows.append(
            {
                "derived_root": rel(root),
                "comparison": "market_year_pair_set",
                "derived_pairs": len(pairs),
                "raw_pairs": len(raw_pairs),
                "canonical_ohlcv_pairs": len(canonical_pairs),
                "missing_vs_raw": len(missing_vs_raw),
                "extra_vs_raw": len(extra_vs_raw),
                "missing_vs_canonical": len(missing_vs_canonical),
                "extra_vs_canonical": len(extra_vs_canonical),
                "status": status,
                "evidence": "metadata_only_pair_comparison_no_raw_row_scan",
            }
        )
    return rows


def compare_raw_and_derived_sample(raw_path: Path, derived_path: Path) -> dict[str, Any]:
    raw_columns, raw_rows, raw_status = parquet_schema(raw_path)
    derived_columns, derived_rows, derived_status = parquet_schema(derived_path)
    key = "ts" if "ts" in derived_columns else "ts_event" if "ts_event" in derived_columns else ""
    raw_key = "ts_event" if "ts_event" in raw_columns else "ts" if "ts" in raw_columns else ""
    common_value_columns = [column for column in OHLCV_COLUMNS if column in raw_columns and column in derived_columns]
    sample_columns = unique_sorted([raw_key, key, "market", "year", "instrument_id", *common_value_columns])
    raw_sample, raw_sample_status = parquet_sample(raw_path, sample_columns)
    derived_sample, derived_sample_status = parquet_sample(derived_path, sample_columns)
    result = {
        "raw_file": rel(raw_path),
        "derived_file": rel(derived_path),
        "raw_rows": raw_rows,
        "derived_rows": derived_rows,
        "raw_schema_status": raw_status,
        "derived_schema_status": derived_status,
        "raw_sample_status": raw_sample_status,
        "derived_sample_status": derived_sample_status,
        "compared_rows": 0,
        "mismatched_rows": 0,
        "duplicate_keys": 0,
        "missing_derived_sample_rows": 0,
        "synthetic_flag_columns": "|".join(column for column in derived_columns if "synthetic" in column.lower() or "fill" in column.lower()),
        "status": "not_compared",
        "evidence": "",
    }
    if raw_sample.empty or derived_sample.empty or not key or not raw_key or not common_value_columns:
        result["status"] = "not_compared"
        result["evidence"] = "missing_sample_or_common_columns"
        return result
    raw_work = raw_sample.rename(columns={raw_key: "ts"})
    derived_work = derived_sample.rename(columns={key: "ts"})
    join_keys = ["ts"]
    for extra_key in ("market", "year", "instrument_id"):
        if extra_key in raw_work.columns and extra_key in derived_work.columns:
            join_keys.append(extra_key)
    result["duplicate_keys"] = int(derived_work.duplicated(subset=join_keys).sum())
    joined = raw_work.merge(derived_work, how="inner", on=join_keys, suffixes=("_raw", "_derived"))
    result["compared_rows"] = int(len(joined))
    result["missing_derived_sample_rows"] = int(max(len(raw_work) - len(joined), 0))
    mismatched = 0
    for _, row in joined.iterrows():
        for column in common_value_columns:
            left = pd.to_numeric(pd.Series([row.get(f"{column}_raw")]), errors="coerce").iloc[0]
            right = pd.to_numeric(pd.Series([row.get(f"{column}_derived")]), errors="coerce").iloc[0]
            if pd.isna(left) or pd.isna(right):
                continue
            if abs(float(left) - float(right)) > max(1e-9, abs(float(left)) * 1e-9):
                mismatched += 1
                break
    result["mismatched_rows"] = int(mismatched)
    result["status"] = "pass" if mismatched == 0 else "mismatch"
    result["evidence"] = "first_row_group_sample"
    return result


def ohlcv_examples(causal_root: Path, raw_root: Path, *, limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for derived_path in sorted(causal_root.glob("*/*.parquet")):
        market, year = parse_market_year(derived_path)
        raw_path = raw_root / market / f"{year}.parquet"
        if not raw_path.exists():
            continue
        rows.append(compare_raw_and_derived_sample(raw_path, derived_path))
        if len(rows) >= limit:
            break
    return rows


def session_audit_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return [
            {
                "folder": rel(root),
                "exists": False,
                "sample_file": "",
                "session_columns_present": False,
                "boundary_columns_present": False,
                "synthetic_rows_marked": False,
                "status": "not_applicable",
                "issue": "session_normalized folder is not present as a separate stage",
            }
        ]
    for path in sorted(root.glob("*/*.parquet"))[:20]:
        columns, row_count, status = parquet_schema(path)
        session_columns = [column for column in columns if "session" in column.lower()]
        boundary_columns = [column for column in columns if "boundary" in column.lower() or column in {"is_session_open", "is_session_close"}]
        synthetic_columns = [column for column in columns if "synthetic" in column.lower() or "fill" in column.lower()]
        rows.append(
            {
                "folder": rel(root),
                "exists": True,
                "sample_file": rel(path),
                "row_count": row_count,
                "session_columns_present": bool(session_columns),
                "session_columns": "|".join(session_columns[:20]),
                "boundary_columns_present": bool(boundary_columns),
                "boundary_columns": "|".join(boundary_columns[:20]),
                "synthetic_rows_marked": bool(synthetic_columns),
                "synthetic_columns": "|".join(synthetic_columns[:20]),
                "status": "pass" if status == "ok" and session_columns and boundary_columns and synthetic_columns else "review",
                "issue": "" if session_columns and boundary_columns and synthetic_columns else "session/synthetic marker columns require review",
            }
        )
    return rows


def causal_audit_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*.parquet"))[:40]:
        columns, row_count, status = parquet_schema(path)
        target_columns = [column for column in columns if column.startswith("target_")]
        future_like_columns = [column for column in columns if "future" in column.lower()]
        lineage_columns = [column for column in ("source_path", "source_file_hash", "source_row_number", "raw_schema_variant") if column in columns]
        causal_columns = [column for column in ("causal_valid", "causal_invalid_reason", "raw_row_present", "is_synthetic") if column in columns]
        rows.append(
            {
                "folder": rel(root),
                "sample_file": rel(path),
                "row_count": row_count,
                "schema_status": status,
                "lineage_columns_present": bool(lineage_columns),
                "lineage_columns": "|".join(lineage_columns),
                "causal_guard_columns_present": bool(causal_columns),
                "causal_guard_columns": "|".join(causal_columns),
                "target_columns_present": bool(target_columns),
                "target_columns": "|".join(target_columns[:20]),
                "future_like_columns": "|".join(future_like_columns[:20]),
                "status": "pass" if status == "ok" and lineage_columns and causal_columns and not target_columns else "review",
                "issue": "target columns present in causal base" if target_columns else "",
            }
        )
    return rows or [
        {
            "folder": rel(root),
            "sample_file": "",
            "row_count": 0,
            "schema_status": "missing",
            "lineage_columns_present": False,
            "causal_guard_columns_present": False,
            "target_columns_present": False,
            "target_columns": "",
            "future_like_columns": "",
            "status": "review",
            "issue": "causal modeling base missing or empty",
        }
    ]


def labels_features_rows(labeled_root: Path, feature_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage, root in (("labels", labeled_root), ("features", feature_root)):
        parquets = parquet_files(root)
        manifest_files = manifest_paths(root)
        sample = parquets[0] if parquets else None
        columns, row_count, status = parquet_schema(sample) if sample else ([], 0, "missing")
        target_columns = [column for column in columns if column.startswith("target_")]
        feature_cols_path = feature_root / "feature_cols.json"
        feature_columns: list[str] = []
        if stage == "features" and feature_cols_path.exists():
            payload = json.loads(feature_cols_path.read_text(encoding="utf-8"))
            feature_columns = list(payload if isinstance(payload, list) else payload.get("features", []))
        forbidden_features = [
            column
            for column in feature_columns
            if column.startswith(FORBIDDEN_FEATURE_PREFIXES) or column in {"target_valid", "target_invalid_reason"}
        ]
        rows.append(
            {
                "stage": stage,
                "folder": rel(root),
                "exists": root.exists(),
                "parquet_count": len(parquets),
                "sample_file": rel(sample) if sample else "",
                "sample_row_count": row_count,
                "schema_status": status,
                "manifest_present": bool(manifest_files or (stage == "features" and feature_cols_path.exists())),
                "manifest_paths": "|".join(manifest_files + ([rel(feature_cols_path)] if feature_cols_path.exists() and stage == "features" else [])),
                "target_columns_present": bool(target_columns),
                "target_columns": "|".join(target_columns[:30]),
                "feature_columns_count": len(feature_columns),
                "forbidden_feature_columns_count": len(forbidden_features),
                "forbidden_feature_columns": "|".join(forbidden_features[:30]),
                "trace_input_folder": "data/causally_gated_normalized" if stage == "labels" else "data/labeled",
                "status": "pass" if status == "ok" and (stage == "labels" or not forbidden_features) else "review",
                "issue": "forbidden feature columns present" if forbidden_features else "",
            }
        )
    return rows


def stale_outputs_rows(lineage_rows: list[dict[str, Any]], active_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in lineage_rows:
        status = str(row.get("current_status", ""))
        folder = str(row.get("folder", ""))
        if status in {"quarantine_candidate", "stale_or_requires_rebuild_review"} or "pre_replace" in folder:
            rows.append(
                {
                    "folder": folder,
                    "stage": row.get("stage", ""),
                    "reason": status,
                    "active_reference_count": sum(1 for ref in active_rows if str(ref.get("path", "")).startswith(folder)),
                    "safe_to_use": False,
                    "recommendation": "Do not use for modeling until explicitly approved or rebuilt from current inputs.",
                }
            )
    return rows


def blockers_from_phase4(
    summary: dict[str, Any],
    mutation_check: dict[str, Any],
    active_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
    raw_vs_rows: list[dict[str, Any]],
    causal_rows: list[dict[str, Any]],
    label_feature_rows: list[dict[str, Any]],
    stale_rows: list[dict[str, Any]],
) -> list[Blocker]:
    blockers = blocker_from_mutation(PHASE, mutation_check)
    if int(summary["phase3_severe_count"]) > 0 or int(summary["phase3_medium_count"]) > 0:
        blockers.append(Blocker("Severe", PHASE, "Phase 3 gate is not clean", rel("reports/data_audit/phase3_ohlcv_reconstruction/phase3_readiness_gate.json"), "Stop before Phase 4."))
    if int(summary["current_modeling_input_folders"]) == 0:
        blockers.append(Blocker("Severe", PHASE, "current modeling input folder not identified", "current_modeling_input_folders=0", "Identify a traceable modeling input before Phase 5."))
    stale_active = [row for row in active_rows if row.get("status") == "stale_or_quarantine_reference" and row.get("operation") in {"read", "write"}]
    if stale_active:
        blockers.append(Blocker("Severe", PHASE, "active script/config references quarantine candidate data path", f"count={len(stale_active)}", "Stop until active references are removed or approved."))
    causal_review = [row for row in causal_rows if row.get("status") != "pass"]
    if causal_review:
        blockers.append(Blocker("Medium", PHASE, "causal modeling base has lineage/causality review findings", f"count={len(causal_review)}", "Review causal audit rows before Phase 5."))
    stale_current = [row for row in stale_rows if row.get("folder") in {"data/labeled", "data/feature_matrices", "data/predictions"} or str(row.get("folder", "")).startswith("data/feature_matrices")]
    if stale_current:
        blockers.append(Blocker("Medium", PHASE, "labels/features/predictions require rebuild review against current causal base", f"count={len(stale_current)}", "Do not use existing labels/features/predictions for modeling until refreshed or approved."))
    raw_mismatch = sum(int(row.get("extra_vs_raw", 0)) for row in raw_vs_rows)
    if raw_mismatch:
        blockers.append(Blocker("Medium", PHASE, "derived market-year extras not present in raw parquet coverage", f"extra_vs_raw={raw_mismatch}", "Review raw-vs-derived coverage before modeling."))
    feature_issues = sum(int(row.get("forbidden_feature_columns_count", 0) or 0) for row in label_feature_rows)
    if feature_issues:
        blockers.append(Blocker("Medium", PHASE, "feature registry contains forbidden feature columns", f"forbidden_feature_columns={feature_issues}", "Remove forbidden features before modeling."))
    quarantine_count = len([row for row in lineage_rows if row.get("classification") == "quarantine_candidate"])
    if quarantine_count:
        blockers.append(Blocker("Low", PHASE, "quarantine candidate derived folders remain present", f"count={quarantine_count}", "Phase 6 may plan quarantine; no execution in Phase 4."))
    blockers.append(Blocker("Low", PHASE, "Phase 3 overlap-risk files excluded by guard", "excluded=2", "Keep overlap guard visible for later gates."))
    blockers.append(Blocker("Low", PHASE, "status KE 2013 caveat carried", "accepted_with_caveat from Phase 2 disposition", "Keep visible for status-dependent modeling gates."))
    return blockers


def render_report(summary: dict[str, Any], blockers: list[Blocker]) -> str:
    lines = [
        "# Phase 4 Derived Lineage and Raw-vs-Derived Audit",
        "",
        f"- Status: `{summary['status']}`",
        f"- Derived folders audited: {summary['derived_folders_audited']}",
        f"- Current modeling input folders: {summary['current_modeling_input_folders_list']}",
        f"- Stale derived folders: {summary['stale_derived_folders']}",
        f"- Unknown derived folders: {summary['unknown_derived_folders']}",
        f"- Active data path references: {summary['active_data_path_references']}",
        f"- Raw-vs-derived comparisons run: {summary['raw_vs_derived_comparisons_run']}",
        f"- Raw-vs-derived mismatches: {summary['raw_vs_derived_mismatches']}",
        f"- Synthetic/fill row findings: {summary['synthetic_fill_row_findings']}",
        f"- Session boundary issues: {summary['session_boundary_issues']}",
        f"- Causality issues: {summary['causality_issues']}",
        f"- Label/feature lineage issues: {summary['label_feature_lineage_issues']}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} | {blocker.evidence}" for blocker in blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_phase4(args: Any) -> dict[str, Any]:
    started = utc_now()
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / "phase4_lineage"
    state_dir = output_dir / "state"
    phase3_gate = json.loads((output_dir / "phase3_ohlcv_reconstruction" / "phase3_readiness_gate.json").read_text(encoding="utf-8"))
    phase3_severe = int(phase3_gate.get("severe_count", 0))
    phase3_medium = int(phase3_gate.get("medium_count", 0))

    before = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_before.csv", before)

    folder_rows = read_csv_rows(output_dir / "phase0_folder_triage" / "folder_classification.csv")
    data_refs = read_csv_rows(output_dir / "phase0_folder_triage" / "data_path_references.csv")
    inventory = read_csv_rows(output_dir / "phase1_raw_inventory" / "inventory.csv")
    config_paths = parse_paths_config(repo_path("configs/alpha_tiered.yaml"))
    config_paths.setdefault("predictions_root", "")
    quarantine_paths = {str(row.get("path", "")) for row in folder_rows if row.get("classification") == "quarantine_candidate"}

    active_rows = active_pipeline_rows(data_refs, config_paths, quarantine_paths)
    lineage_rows = folder_lineage_rows(folder_rows)
    raw_root = repo_path(config_paths.get("raw_root", "data/raw"))
    causal_root = repo_path(config_paths.get("causal_base_root", "data/causally_gated_normalized"))
    labeled_root = repo_path(config_paths.get("labeled_root", "data/labeled"))
    feature_root = repo_path(config_paths.get("feature_matrix_root", "data/feature_matrices/baseline"))
    raw_pairs = parquet_pairs(raw_root)
    canonical_pairs = inventory_pairs(inventory, "ohlcv-1m")
    raw_vs_roots = {
        "causally_gated_normalized": causal_root,
        "labeled": labeled_root,
        "feature_matrices": feature_root,
    }
    if config_paths.get("predictions_root"):
        raw_vs_roots["predictions"] = repo_path(config_paths["predictions_root"])
    raw_vs_rows = raw_vs_derived_rows(raw_pairs, canonical_pairs, raw_vs_roots)
    ohlcv_rows = ohlcv_examples(causal_root, raw_root)
    session_rows = session_audit_rows(causal_root if not repo_path("data/session_normalized").exists() else repo_path("data/session_normalized"))
    causal_rows = causal_audit_rows(causal_root)
    label_feature_rows = labels_features_rows(labeled_root, feature_root)
    stale_rows = stale_outputs_rows(lineage_rows, active_rows)

    after = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    write_source_manifest(state_dir / "source_manifest_after.csv", after)
    mutation_check = compare_source_manifests(before, after)
    write_json(state_dir / "source_mutation_check.json", mutation_check)

    current_modeling = [
        row["folder"]
        for row in lineage_rows
        if row.get("folder") in CURRENT_MODELING_ROOTS and row.get("exists") is True
    ]
    raw_vs_mismatches = sum(int(row.get("mismatched_rows", 0) or 0) for row in ohlcv_rows)
    raw_vs_mismatches += sum(int(row.get("extra_vs_raw", 0) or 0) for row in raw_vs_rows)
    synthetic_findings = sum(1 for row in session_rows if row.get("synthetic_rows_marked") is False and row.get("exists") is True)
    session_issues = sum(1 for row in session_rows if row.get("status") == "review")
    causality_issues = sum(1 for row in causal_rows if row.get("status") != "pass")
    label_feature_issues = sum(1 for row in label_feature_rows if row.get("status") != "pass")
    stale_folder_list = unique_sorted(row["folder"] for row in stale_rows)
    unknown_folder_list = unique_sorted(row["folder"] for row in lineage_rows if row.get("classification") in {"unsafe_unknown", "missing_expected"})

    summary = {
        "phase3_severe_count": phase3_severe,
        "phase3_medium_count": phase3_medium,
        "derived_folders_audited": len(lineage_rows),
        "derived_folders_audited_list": unique_sorted(row["folder"] for row in lineage_rows),
        "current_modeling_input_folders": len(current_modeling),
        "current_modeling_input_folders_list": "|".join(current_modeling),
        "stale_derived_folders": len(stale_folder_list),
        "stale_derived_folders_list": "|".join(stale_folder_list),
        "unknown_derived_folders": len(unknown_folder_list),
        "unknown_derived_folders_list": "|".join(unknown_folder_list),
        "active_data_path_references": len(active_rows),
        "raw_vs_derived_comparisons_run": len(raw_vs_rows) + len(ohlcv_rows),
        "raw_vs_derived_mismatches": raw_vs_mismatches,
        "synthetic_fill_row_findings": synthetic_findings,
        "session_boundary_issues": session_issues,
        "causality_issues": causality_issues,
        "label_feature_lineage_issues": label_feature_issues,
        "source_mutation_check": mutation_check["source_mutation_check"],
    }

    blockers = blockers_from_phase4(summary, mutation_check, active_rows, lineage_rows, raw_vs_rows, causal_rows, label_feature_rows, stale_rows)
    severe = sum(1 for blocker in blockers if blocker.severity == "Severe")
    medium = sum(1 for blocker in blockers if blocker.severity == "Medium")
    low = sum(1 for blocker in blockers if blocker.severity == "Low")
    summary.update(
        {
            "status": "fail" if severe else "pass_with_medium_blockers" if medium else "pass",
            "severe_issue_count": severe,
            "medium_issue_count": medium,
            "low_issue_count": low,
        }
    )

    reports = [
        phase_dir / "active_pipeline_inputs.csv",
        phase_dir / "derived_folder_lineage.csv",
        phase_dir / "raw_vs_derived_audit.csv",
        phase_dir / "ohlcv_raw_vs_derived_examples.csv",
        phase_dir / "session_normalized_audit.csv",
        phase_dir / "causally_gated_audit.csv",
        phase_dir / "labels_features_lineage_audit.csv",
        phase_dir / "stale_derived_outputs.csv",
        phase_dir / "blockers.csv",
        phase_dir / "phase4_readiness_gate.json",
        phase_dir / "phase4_report.md",
    ]
    write_csv(phase_dir / "active_pipeline_inputs.csv", ["item_type", "name", "path", "role", "source_file", "line", "operation", "context", "status", "issue", "evidence"], active_rows)
    write_csv(phase_dir / "derived_folder_lineage.csv", list(lineage_rows[0].keys()) if lineage_rows else ["folder"], lineage_rows)
    write_csv(phase_dir / "raw_vs_derived_audit.csv", list(raw_vs_rows[0].keys()) if raw_vs_rows else ["derived_root"], raw_vs_rows)
    write_csv(phase_dir / "ohlcv_raw_vs_derived_examples.csv", list(ohlcv_rows[0].keys()) if ohlcv_rows else ["raw_file"], ohlcv_rows)
    write_csv(phase_dir / "session_normalized_audit.csv", list(session_rows[0].keys()) if session_rows else ["folder"], session_rows)
    write_csv(phase_dir / "causally_gated_audit.csv", list(causal_rows[0].keys()) if causal_rows else ["folder"], causal_rows)
    write_csv(phase_dir / "labels_features_lineage_audit.csv", list(label_feature_rows[0].keys()) if label_feature_rows else ["stage"], label_feature_rows)
    write_csv(phase_dir / "stale_derived_outputs.csv", list(stale_rows[0].keys()) if stale_rows else ["folder", "stage", "reason", "active_reference_count", "safe_to_use", "recommendation"], stale_rows)

    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=utc_now(),
        reports=[rel(path) for path in reports],
        blockers=blockers,
        source_mutation_check=str(mutation_check["source_mutation_check"]),
        summary=summary,
        gate_path=phase_gate_path(Path(args.output_dir), 4, "phase4_readiness_gate.json"),
        blockers_csv=phase_dir / "blockers.csv",
    )
    write_text(phase_dir / "phase4_report.md", render_report(summary, blockers))
    gate = write_phase_outputs(result)
    state = {
        "last_phase": PHASE,
        "last_gate": rel(result.gate_path),
        "updated_at": utc_now(),
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
        "sample": bool(args.sample),
        "full": bool(args.full),
        "allow_full_scan": bool(args.allow_full_scan),
        "gate": gate,
    }
    write_json(state_dir / "audit_state.json", state)
    print(
        "phase4 status={status} severe={severe} medium={medium} low={low} derived_folders={folders} current_modeling_inputs={modeling} raw_vs_derived_mismatches={mismatches} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            folders=summary["derived_folders_audited"],
            modeling=summary["current_modeling_input_folders"],
            mismatches=summary["raw_vs_derived_mismatches"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate
